import time
import os
import subprocess as sp
import re
import configparser
from collections import OrderedDict
from enum import Enum


# Task status
class Status(Enum):
    wait = 0
    done = 1
    run = 2
    fail = 3
    queue = 4


class Task:

    def __init__(self,
                 directory,
                 name,
                 pbs='.pbs',
                 out='.out',
                 error='.error',
                 status=Status.wait):
        self.directory = directory
        self.name = name
        self.pbs = os.path.join(self.directory, self.name + pbs)
        self.out = os.path.join(self.directory, self.name + out)
        self.error = os.path.join(self.directory, self.name + error)
        self.status = status
        self.time = None  # done time

    def __str__(self):
        if self.time:
            return f'Task {self.name} {self.status} {self.time}'
        else:
            return f'Task {self.name} {self.status}'

    __repr__ = __str__


class PBS():

    def __init__(self,
                 directory='',
                 pbs_template='pbs_template',
                 queue_name='slst_zhangly',
                 use_temp=False,
                 node=1,
                 ppn=8,
                 **args):

        self.args = {}
        self.args['queue_name'] = queue_name
        self.args['node'] = node
        self.args['ppn'] = ppn

        self.working_directory = os.path.abspath(directory)

        self.pbs_template = self.find_file(pbs_template)

        with open(self.pbs_template, 'r', encoding='utf-8') as f:
            self.template = f.read()

        self.store_tasks = OrderedDict()
        self.command_file = None
        self.use_temp = use_temp
        self.temp_dir = '~/tempdir'
        self.pbs_directory = ''

    def find_file(self, file):
        if os.path.exists(file):
            return file
        elif os.path.exists(os.path.join(self.working_directory, file)):
            return os.path.join(self.working_directory, file)
        else:
            raise AssertionError(f'can\'t find {file}')

    def set_script(self, script_file='00-pbs.sh'):

        self.command_file = self.find_file(script_file)

        with open(self.command_file, encoding='utf-8') as f:
            self.command = f.readlines()

        self.command = [i.strip() for i in self.command]
        self.command = os.linesep.join(self.command) + os.linesep

        self.command = re.sub(r'^\%.*?\n', '', self.command)

        env = re.search(r'env=(\w+?)\n', self.command)

        if not 'set -euxo pipefail' in self.command:
            self.command = 'set -euxo pipefail\n' + self.command + 'set +euxo pipefail\n'

        if env:
            env_name = env.group(1)
            conda = sp.run(f'which conda', shell=True, capture_output=True)
            path_to_conda = conda.stdout.decode().strip().replace(
                'bin/conda', 'etc/profile.d/conda.sh')
            if not f'conda activate' in self.command:
                self.command = f'source {path_to_conda}\nconda activate {env_name}\n' + \
                    self.command + f'conda deactivate\n'

#         self.command = re.sub(r'echo (.*?) ',r'\1 ', self.command)

    def get_running_tasks(self):
        running_tasks = []
        queuing_tasks = []
        result = sp.run(f'qstat', shell=True, capture_output=True)
        result = result.stdout.decode().split('\n')[2:-1]
        for i in result:
            task = re.match(r'(\S*)\s*(\S*)\s*(\S*)\s*(\S*)\s*(R|Q)\s*(\S*)\s*',
                            i)
            if task.group(5) == 'R':
                running_tasks.append(task.group(2))
            if task.group(5) == 'Q':
                queuing_tasks.append(task.group(2))
        return running_tasks, queuing_tasks

    def set_task_directory(self, directory=''):
        if directory:
            if os.path.exists(directory):
                self.pbs_directory = directory
            elif os.path.exists(os.path.join(self.working_directory,
                                             directory)):
                self.pbs_directory = os.path.join(self.working_directory,
                                                  directory)
            else:
                return
        else:
            return

        with open(f'{self.pbs_directory}/template.sh', 'r',
                  encoding='utf-8') as f:
            self.command = f.read()

        files = [i for i in os.listdir(self.pbs_directory) if i.endswith('pbs')]
        if not files:
            return

        tasks = [i.split('.')[-2] for i in files]
        running_tasks, queuing_tasks = self.get_running_tasks()
        for task in tasks:
            _task = Task(self.pbs_directory, task)
            if task in running_tasks:
                _task.status = Status.run
            elif task in queuing_tasks:
                _task.status = Status.queue
            elif os.path.exists(_task.out):
                with open(_task.out) as f:
                    line = f.readlines()[-1]
                    if line.startswith('time used'):
                        time = re.search(r'^time used (.*)', line).group(1)
                        _task.time = time
                        _task.status = Status.done
                    else:
                        _task.status = Status.fail

            self.store_tasks[task] = _task

        return self.store_tasks

    def generate(self,
                 task_config,
                 single_task_time=48,
                 pbs_directory_name=None):
        assert isinstance(task_config, dict)
        if not self.command_file:
            print('should run command first.')
            return
        directory, name = os.path.split(self.command_file)
        if not pbs_directory_name:
            self.pbs_directory = os.path.join(self.working_directory,
                                              os.path.splitext(name)[0])
        else:
            self.pbs_directory = os.path.join(self.working_directory,
                                              pbs_directory_name)

        if not os.path.exists(self.pbs_directory):
            os.mkdir(self.pbs_directory)

#         with open(f'{self.pbs_directory}/template.sh', 'w',
#                   encoding='utf-8') as f:
#             f.write(self.command)

        variables = {}
        for key, value in task_config.items():
            path = self.find_file(value)
            assert os.path.exists(path), f'{path} doesn\'t exist'
            with open(path, 'r', encoding='utf-8') as f:
                variables[key] = [i.strip() for i in f.readlines()]
        length = list(set([len(i) for i in variables.values()]))
        assert len(length) == 1, 'length of variables not consistent'

        for i in range(length[0]):
            command = self.command

            names = []
            for key in variables.keys():
                command = re.sub(f'{key}=\S+?\n',
                                 f'{key}={variables[key][i]}\n', command)
                names.append(variables[key][i])

            task = '_'.join(names)

            _task = Task(self.pbs_directory, task)
            self.store_tasks[task] = _task

            if self.use_temp:
                tempdir = os.path.join(self.temp_dir, task)
                command = f'export TMPDIR={tempdir}\nmkdir -p $TMPDIR\n' + \
                    command + '\nrm -rf $TMPDIR\nexport TMPDIR='

            template = self.template.format(task_name=task,
                                            task_time=single_task_time,
                                            out=_task.out,
                                            error=_task.error,
                                            command=command,
                                            **self.args)

            with open(_task.pbs, 'w', encoding='utf-8') as f:
                f.write(template)
            print(f'{task} generated')

    def generate_one(self, task, single_task_time=48, pbs_directory_name=None):
        assert isinstance(task, str)
        if pbs_directory_name is None:
            pbs_directory_name = 'pbs'

        self.pbs_directory = os.path.join(self.working_directory,
                                          pbs_directory_name)
        if not os.path.exists(self.pbs_directory):
            os.mkdir(self.pbs_directory)


#         with open(f'{self.pbs_directory}/{task}.sh', 'w',
#                   encoding='utf-8') as f:
#             f.write(self.command)

        _task = Task(self.pbs_directory, task)
        self.store_tasks[task] = _task

        template = self.template.format(task_name=task,
                                        task_time=single_task_time,
                                        out=_task.out,
                                        error=_task.error,
                                        command=self.command,
                                        **self.args)

        with open(_task.pbs, 'w', encoding='utf-8') as f:
            f.write(template)
        print(f'{task} generated')

    def get(self, task):
        assert task in self.store_tasks, f"{task} not in task_names"
        return self.store_tasks.get(task)

    def __getitem__(self, n):
        return list(self.store_tasks.values())[n]

    def _qsub(self, _task, ignore_done=True):
        assert isinstance(_task, Task)
        if ignore_done and _task.status in [Status.done, Status.run]:
            return
        for file in [_task.out, _task.error]:
            if os.path.exists(file):
                os.remove(file)
        result = sp.run(f'qsub {_task.pbs}', shell=True)
        if result.returncode == 0:
            print(f"qsub success: {_task.name}")
            _task.status = Status.run
            _task.time = None
            self.store_tasks[_task.name] = _task
        else:
            print(f"qsub error: {_task.name}")
            _task.status = Status.fail
            _task.time = None
            self.store_tasks[_task.name] = _task

    def qsub(self, task, wait_time=3, ignore_done=True):
        if isinstance(task, str):
            if not self.get(task):
                raise AssertionError(f'Can\'t find {task}')
            else:
                self._qsub(self.get(task), ignore_done)

        elif isinstance(task, (list, tuple, set)):
            for i in task:
                self.qsub(i, ignore_done=ignore_done)
                time.sleep(wait_time)
        else:
            self._qsub(task, ignore_done)

    def clear_tasks(self):
        self.store_tasks = OrderedDict()

    def check_tasks(self):
        for i in self.store_tasks:
            if i.status == 'done':
                print(i)

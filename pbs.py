import os
import subprocess as sp
import copy
import time
import re
import configparser
from collections import namedtuple


class PBS():
    Task = namedtuple('Task', ['pbs', 'out', 'error'])

    def __init__(self, directory='', queue_name='slst_zhangly', node=1, ppn=10, pbs_template='pbs_template', **args):

        assert os.path.exists(pbs_template), f'{pbs_template} doesn\'t exist'
        self.args = {}
        self.args['queue_name'] = queue_name
        self.args['node'] = 1
        self.args['ppn'] = 10

        self.working_directory = os.path.abspath(directory)

        with open(pbs_template, 'r', encoding='utf-8') as f:
            self.template = f.read()

        self.store_tasks = {}
        self.command_file = None

    def command(self, file):
        self.command_file = file
        assert os.path.exists(
            self.command_file), f'{self.command_file} doesn\'t exist'

        with open(file, encoding='utf-8') as f:
            self.command = f.readlines()
        self.command = [i.strip() for i in self.command]
        self.command = os.linesep.join(self.command) + os.linesep

        # self.command = re.sub(r'^\%.*?\n', '', self.command)

        if not 'set -euxo pipefail\n' in self.command:
            self.command = 'set -euxo pipefail\n' + self.command

        env = re.search(r'env=(\w+?)\n', self.command)
        if env:
            env_name = env.group(1)
            conda = sp.run(f'which conda', shell=True, capture_output=True)
            path_to_conda = conda.stdout.decode().strip().replace('bin/conda', 'bin')
            if not f'source {path_to_conda}/activate {env_name}\n' in self.command:
                self.command = f'source {path_to_conda}/activate {env_name}\n' + \
                    self.command + f'source {path_to_conda}/deactivate\n'

        with open(self.command_file, 'w', encoding='utf-8') as f:
            f.write(self.command)

        # self.command = re.sub(r'echo (.*?) ',r'\1', self.command)

    def generate(self, task_config, single_task_time, pbs_directory_name=None):
        if not self.command_file:
            print('should run command first.')
            return
        if not pbs_directory_name:
            self.pbs_directory_name = os.path.splitext(
                os.path.basename(self.command_file))[0] + '_pbs'
        else:
            self.pbs_directory_name = pbs_directory_name
        sp.run(
            f'mkdir -p {self.working_directory}/{self.pbs_directory_name}/', shell=True)

        variables = {}
        for key, value in task_config.items():
            path = os.path.join(self.working_directory, value)
            assert os.path.exists(path), f'{path} doesn\'t exist'
            with open(path, 'r', encoding='utf-8') as f:
                variables[key] = [i.strip() for i in f.readlines()]
        length = list(set([len(i) for i in variables.values()]))
        assert len(length) == 1, 'length of variables not consistent'

        for i in range(length[0]):
            command = self.command

            names = []
            for key in variables.keys():
                command = re.sub(
                    f'{key}=\S+?\n', f'{key}={variables[key][i]}\n', command)
                names.append(variables[key][i])

            task = '_'.join(names)
            task_files = [f'{self.working_directory}/{self.pbs_directory_name}/{task}' +
                          i for i in ['.pbs', '.out', '.error']]

            _task = PBS.Task(*task_files)
            self.store_tasks[task] = _task

            template = self.template.format(
                task_name=task, task_time=single_task_time, out=_task.out, error=_task.error, command=command, **self.args)

            with open(_task.pbs, 'w', encoding='utf-8') as f:
                f.write(template)

    def generate_one(self, task, single_task_time, pbs_directory_name=None):
        if not pbs_directory_name:
            self.pbs_directory_name = 'pbs'
        else:
            self.pbs_directory_name = pbs_directory_name
        sp.run(
            f'mkdir -p {self.working_directory}/{self.pbs_directory_name}/', shell=True)
        task_files = [f'{self.working_directory}/{self.pbs_directory_name}/{task}' +
                      i for i in ['.pbs', '.out', '.error']]
        _task = PBS.Task(*task_files)
        self.store_tasks[task] = _task

        template = self.template.format(task_name=task, task_time=single_task_time,
                                        out=_task.out, error=_task.error, command=self.command, **self.args)

        with open(_task.pbs, 'w', encoding='utf-8') as f:
            f.write(template)

    def qsub_all(self):
        if not self.store_tasks:
            print('should run generate function first.')
            return

        for task in self.store_tasks.items():
            _task = self.get(task)
            result = sp.run(f'qsub {_task.pbs}', shell=True)
            if result.returncode == 0:
                print(f"qsub success: {task}")
            else:
                print(f"qsub error: {task}")
            time.sleep(5)

    def re_qsub_all(self):
        if not self.store_tasks:
            print('should run generate function first.')
            return

        running_tasks = self.get_running_tasks()
        for task in self.store_tasks:
            if （not self.check_task_done(task)) and (task not in running_tasks):
                _task=self.get(task)
                result=sp.run(f'qsub {_task.pbs}', shell = True)
                if result.returncode == 0:
                    print(f"re qsub success: {task}")
                else:
                    print(f"re qsub error: {task}")
                time.sleep(5)

    def qsub(self, task):
        if not self.store_tasks:
            print('should run generate function first.')
            return

        _task=self.get(task)
        sp.run(f'rm {_task.out} {_task.error}', shell = True)
        result=sp.run(f'qsub {_task.pbs}', shell = True)
        if result.returncode == 0:
            print(f"qsub success: {task}")
        else:
            print(f"qsub error: {task}")

    def get_running_tasks(self):
        tasks=[]
        import re
        result=sp.run(f'qstat', shell = True, capture_output = True)
        result=result.stdout.decode().split('\n')[2:-1]
        for i in result:
            task=re.match(
                r'(\S*)\s*(\S*)\s*(\S*)\s*(\S*)\s*(\S*)\s*(\S*)\s*', i).group(2)
            tasks.append(task)
        return tasks

    def clear_tasks(self):
        self.store_tasks={}

    def check_tasks_done(self):
        if all([self.check_task_done(task) for task in self.store_tasks]):
            print('all tasks done')

    def get(self, task):
        assert task in self.store_tasks, f"{task} not in task_names"
        return self.store_tasks.get(task)

    def check_task_done(self, task):
        _task=self.get(task)
        if os.path.exists(_task.out):
            with open(_task.out) as f:
                lines=f.readlines()
            if len([line for line in lines if line.startswith('---')]) == 2:
                return True
        else:
            return False

    def analyze():
        # analyze time
        pass

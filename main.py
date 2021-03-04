from pbs import PBS
import re
import os
import argparse
import configparser


def main(pbs_config, pbs_template):
    assert os.path.exists(
        pbs_template), "cann't find pbs_template, make sure it is under the same directory of main.py"
    assert os.path.exists(pbs_config), f"{pbs_config} doesn't exists"

    pbs_template = os.path.abspath(pbs_template)
    cf = configparser.ConfigParser()
    cf.read(pbs_config)
    config = dict(cf.items("PBS_config"))
    assert not any([bool(re.search('<.*>', i))
                    for i in config.values()]), 'config file <data> must be filled'
    file_directory = config.get('file_directory')
    if file_directory and os.path.isdir(file_directory):
        os.chdir(file_directory)
    else:
        raise Exception(f"directory {file_directory} doesn't exists")
    pbs = PBS(directory=file_directory,
              pbs_template=pbs_template, **config)
    pbs.command(config['script_file'])
    if config['multiple'].lower() == 'true':
        multiple_config = dict(cf.items("multiple"))
        multiple(pbs, multiple_config)
    elif config['multiple'].lower() == 'false':
        single_config = dict(cf.items("single"))
        single(pbs, single_config)
    else:
        print('multiple item of pbs_config was set wrong, must be true or false')


def multiple(pbs, config):
    assert not any([bool(re.search('<.*>', i))
                    for i in config.values()]), 'config file <data> must be filled'
    task_config = {}
    for i in config:
        result = re.match('variable(\d+)', i)
        if result:
            number = result.group(1)
            assert f'variable{number}_file' in config, 'variable{number} does\' have corresponding file'
            task_config[config[f'variable{number}']
                        ] = config[f'variable{number}_file']
    assert task_config, 'at least one variable specified'

    time = config.get('time')
    pbs_directory_name = config.get('pbs_directory_name')
    pbs.generate(task_config, time, pbs_directory_name)


def single(pbs, config):
    assert not any([bool(re.search('<.*>', i))
                    for i in config.values()]), 'config file <data> must be filled'
    task_name = config.get('task_name')
    time = config.get('time')
    pbs_directory_name = config.get('pbs_directory_name')
    pbs.generate_one(task_name, time, pbs_directory_name)


if __name__ == "__main__":
    import sys
    pbs_template = os.path.split(sys.argv[0])[0] + '/pbs_template'
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('ini', type=str, help='config file')
    args = parser.parse_args()
    main(args.ini, pbs_template)

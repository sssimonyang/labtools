# PBS generator

Generate pbs based on config and template.

## Usage
```
python main.py <pbs_config>
```

## pbs_config

Config file is pbs_config.
```
[PBS_config]
# file_directory = <file_directory>
# file_directory, by default current working directory
# script_file and all variable_file must under file_directory, the the output will write to file_directory
script_file = <script_file_name>
queue_name = <queue_name>
node = 1
ppn = 10
multiple = true
# multiple determine the mode
# if true it will use multiple section and generate multiple pbs
# if false it will use single section and generate one pbs
# default true

[multiple]
time = <hours of time>
variable1 = <variable1>
variable1_file = <variable1_file>
# variable2 = <variable2>
# variable2_file = <variable2_file>
# variable3
# variable3_file
# ...
# ...
# pbs_directory_name = <queue_name> 
# pbs_directory_name, by default <script_file_name>_pbs

[single]
time = <hours of time>
task_name = <task_name>
# pbs_directory_name = <queue_name> 
# pbs_directory_name, by default pbs
```
Copy, fill all place enclosed by angle brackets, remove `#` to add more config.

File_directory is by default current working directory, and script_file and all variable_file must be put under file_directory, then the generated file will be written to file_directory correctly.

It have two modes, multiple (multiple = true) and single (multiple = false) and read the corresponding section.

## feature
1. It will automaticly detect env. If `env=<env_name>` was found in given script file, it will add `source <path_to_conda>/activate <env_name>` in head and `source <path_to_conda>/deactivate` in tail.
2. It will add `set -euxo pipefail` in the head of given script file to avoid continuing running after error.
3. The two change metioned above will modify raw script file directly.
3. The pbs_template output start line and end line with time to help calculate the used time of script.


## mode
### multiple
You can specify varibales.

Here is an example.
```
variable1 = patient
variable1_file = patients
```
The patients must exist under file_directory and have multiple values.

An example of cotennt of patients.
```
A_patient
B_patient
C_patient
```
And make sure there is an line `patient=<some_patient>` in given script file. It will replace `<some_patient>` as given variable1_file.

This type of variable can have one or more, if more than one, make sure the num of values consistent.

### single
Single mode is just a simplst version if multiple.

## Other hint
PBS class in pbs can be used by import and have qsub and other task submit related function.

## pbs_template
```
#!/bin/sh
#PBS -N {task_name}
#PBS -l nodes={node}:ppn={ppn}
#PBS -l walltime={task_time}:00:00
#PBS -S /bin/bash
#PBS -q {queue_name}
#PBS -o {out}
#PBS -e {error}
start='------------START------------'$(date "+%Y %h %d %H:%M:%S")'------------START------------'
echo $start
echo $start >&2

{command}

end='-------------END-------------'$(date "+%Y %h %d %H:%M:%S")'-------------END-------------'
echo $end
echo $end >&2
```

## todo
1. setup.
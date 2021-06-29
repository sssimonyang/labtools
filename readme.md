# PBS generator

Generate pbs based on config and template.

## Usage
```
python main.py <pbs_config>
```

## pbs_config

Config file is pbs_config.ini.
```
[PBS_config]
file_directory = <file_directory>
script_file = <script_file_name>
# script_file must under file_directory
pbs_queue_name = <queue_name>
node = 1
ppn = 10
multiple = true
# multiple determine the mode
# if true it will use multiple section and generate multiple pbs
# if false it will use single section and generate one pbs
# default true

[multiple]
time = <hours of time>
variable1 = patient
variable1_file = patients
# variable2 = <variable1>
# variable2_file = <variable1_file>
# variable3
# variable3_file
# ...
# ...
# all variable_file must under file_directory specified in file_directory
# pbs_directory_name = <directory_name> 
# pbs_directory_name, by default {script_file_name}

[single]
time = <hours of time>
task_name = <task_name>
# pbs_directory_name = <directory_name> 
# pbs_directory_name, by default pbs
```
Copy, fill all place enclosed by angle brackets, remove `#` to add more config. One example is in exmaple directory.

File_directory is by default the working directory, and script_file and all variable_file must be put under file_directory, then the generated file will be written to file_directory correctly.

It have two modes, multiple (multiple = true) and single (multiple = false) and read the corresponding section.

## feature
1. It will automaticly detect env. If `env=<env_name>` was found in given script file, it will add `source <path_to_conda>/nconda activate <env_name>` in head and `conda deactivate` in tail.
2. It will add `set -euxo pipefail` in the head and `set +euxo pipefail` in the tail to given script file, avoiding continuing running after error.
3. The pbs_template output time in start and end and calculate the runtime.


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
And make sure there is an line `patient=<some_patient>` in given script file. It will replace `<some_patient>` as given value from variable1_file.

This type of variable can have one or more, if more than one, make sure the num of values consistent.

### single
Single mode is just a simplst version of multiple.

## Other hint
PBS class in pbs can be used by import and it has qsub and other task related function.

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

timer(){{
    timer_start=$*
    timer_end=`date "+%Y-%m-%d %H:%M:%S"`
    duration=`echo $(($(date +%s -d "${{timer_end}}") - $(date +%s -d "${{timer_start}}"))) | awk '{{t=split("60 s 60 m 24 h 999 d",a);for(n=1;n<t;n+=2){{if($1==0)break;s=$1%a[n]a[n+1]s;$1=int($1/a[n])}}print s}}'`
    echo "time used "${{duration}}
}}

timer_start=`date "+%Y-%m-%d %H:%M:%S"`

start='------------START------------'${{timer_start}}'------------START------------'
echo $start
echo $start >&2

{command}

timer_end=`date "+%Y-%m-%d %H:%M:%S"`
end='-------------END-------------'${{timer_end}}'-------------END-------------'
echo $end
echo $end >&2
timer ${{timer_start}}
timer ${{timer_start}} >&2

```

## example

One example is in example directory.

```
$ python main.py example/example.ini
TCGA-DD-A113 generated
TCGA-DD-A115 generated
TCGA-DD-A116 generated
TCGA-DD-A119 generated
TCGA-DD-A11A generated
```

## todo
1. setup.
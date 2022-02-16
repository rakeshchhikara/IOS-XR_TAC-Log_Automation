# Author: Rakesh Kumar

# Usage: This script has Five options that user can choose.
# To run show tech commands in "IOS-XR mode" and upload file/s to TAC case Choose: 1
# To run show tech commands in "Admin mode" and upload file/s to TAC case Choose:  2
# To upload already generated or saved file/s to TAC case Choose: 3
# To run Only SHOW commands , capture output to file and upload it to TAC case Choose: 4
# To upload existing file on Local machine/JumpHost to TAC case: 5

# version 1.0
import gzip
import time
import os
from netmiko import ConnectHandler
import paramiko
from scp import SCPClient
import hashlib
import getpass
import urllib3
import requests
from requests.auth import HTTPBasicAuth
from tqdm import tqdm
from tqdm.utils import CallbackIOWrapper


# This function is take user input for commands/files and connect to device.
def initial_func(user_prompt):
    lines = []
    while True:
        line = input(user_prompt)

        if line:
            lines.append(line)
        else:
            break

    print(f'\nNow connecting to device...')
    connection = ConnectHandler(**device)
    prompt = connection.find_prompt()
    prompt_strip = prompt.find(':') + 1
    hostname = prompt[prompt_strip:-1]
    return connection, prompt, hostname, lines


# This function will check free space on harddisk and will only execute show tech commands if free space more than 15%
def space_check():
    output = connection.send_command('dir harddisk: | i kbytes')
    location1 = output.find('\n')
    location2 = output.find('kbytes total') - 1
    total_space = int(output[location1:location2])

    location3 = output.find('(') + 1
    location4 = output.find('kbytes free') - 1
    free_space = int(output[location3:location4])

    free_percent = (free_space / total_space) * 100
    free_percent = round(free_percent, 2)

    if free_percent < 15:
        print(f'Free space available on Harddisk is only {free_percent}%. '
              f'Free up some space first and then re-run script. Free space should be more than 15% to continue.')
        quit()
    else:
        print(f'\n{100*"*"}\nFree space on harddisk is {free_percent}%. We will continue.\n{100*"*"}\n')


def create_local_dir():
    script_directory = os.getcwd()
    new_dir = 'SR' + sr_username
    if os.path.exists(script_directory + '/' + new_dir) is False:
        os.mkdir(new_dir)
        os.chdir(new_dir)
    else:
        os.chdir(new_dir)
    log_directory = os.getcwd()
    return log_directory


# This function is for running IOS-XR mode show tech commands one at a time and capture filename with path.
def run_cmd():
    try:
        print(f'\nGenerating "{user_cmd}" on device {hostname}. Please wait...\n')
        output = connection.send_command(user_cmd, max_loops=50000)
    except Exception as err:
        print('Some error happened - ', err)
    else:
        if ('^' in output) or ('syntax error' in output) or ('Incomplete command' in output):
            print(
                f'Entered command - "{user_cmd}" is Invalid or Incomplete. Please re-check correct command.\n{120 * "#"}')
        else:
            print(output)
            # Store show-tech file name and path on device in 'filename' variable.
            file_start_loc = output.find('/harddisk')
            file_end_loc = output.find('.tgz') + 4
            filename = output[file_start_loc:file_end_loc]
            return filename


# This function is download the captured file from device to local machine/JumpServer.
def retrieve_file(port):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(device_ip, port, username, password, timeout=20)
    try:
        scp = SCPClient(client.get_transport())
        scp.get(filename)
    except Exception as e:
        print(f'\n *** Some Exception occurred while retrieving file to local machine. Exception detail: {e}\n')

        # If exception happened however file is copied.
        loc1 = filename.rfind('/') + 1
        local_file_name = filename[loc1:]  # Grabbing only name of file. Stripped path.
        if os.path.exists(local_file_name) is True:
            print(f'\nFile "{filename}" copied to local machine\n')
            return local_file_name
        else:
            failed_list.append(user_cmd)
    else:
        print(f'\nFile "{filename}" copied to local machine\n')
        loc1 = filename.rfind('/') + 1
        local_file_name = filename[loc1:]  # Grabbing only name of file. Stripped path.
        return local_file_name


# This function is to check MD5 hash value of file on Device.
def remote_md5_check():
    try:
        print(f'\nCalculating md5 hash of file "{filename}" on device... please wait.')
        check_md5 = connection.send_command_expect('show md5 file ' + filename, max_loops=5000, delay_factor=5)

        remote_md5 = check_md5[28:]
    except Exception as err:
        print(f'Some exception occurred while performing remote md5 check: {err}\n{100*"#"}')
    else:
        return remote_md5


# This function is to check MD5 hash value of copied file to Local machine/Jump Server.
def local_md5_check():
    try:
        print(f'\nCalculating md5 hash of Local file "{local_file_name}" ... please wait.')

        # Calculating MD5 hash value of local file
        md5_hash = hashlib.md5()
        with open(local_file_name, "rb") as f:
            # Read and update hash in chunks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                md5_hash.update(byte_block)
            md5_local = (md5_hash.hexdigest())
    except Exception as err:
        print(f'Some exception occurred while performing md5 check on local file: {err}\n{100*"#"}')
    else:
        return md5_local


# This function is to compare both local and remote MD5 hashes.
def md5_compare():
    print(f'\nMD5 calculated on Device: {remote_md5}')
    print(f'Local md5 calculated: {md5_local}')
    if remote_md5 == md5_local:
        print(f'MD5 has matched. Download successful.\n{120 * "#"}')
        local_files.append(local_file_name)
    else:
        print(f'MD5 has mismatch. Check again.\n{120 * "#"}')


# This function is to run Admin mode show tech commands and copy the file to
# IOS-XR mode in "/harddisk/showtech/" directory.
def run_cmd_admin():
    print(f'Entering in Admin mode to generate Admin specific show tech of command - "{user_cmd}"')
    connection.send_command('admin', expect_string=r'sysadmin')

    try:
        print(f'\nGenerating "{user_cmd}" on device {hostname}. Please wait...\n')
        output = connection.send_command(user_cmd, max_loops=50000)
    except Exception as err:
        print(f'Some error occurred while running command - "{user_cmd} : {err}\n{100*"#"}')
    else:
        if ('^' in output) or ('syntax error' in output) or ('Incomplete command' in output):
            print(
                f'Entered command - "{user_cmd}" is Incomplete or Invalid. Please re-check correct command.\n{120 * "#"}')
        else:
            print(output)
            file_start_loc = output.find('/')
            file_end_loc = output.find('.tgz') + 4
            filename = output[file_start_loc:file_end_loc]
            try:
                print('\nCopying file to IOS-XR mode')
                copy_cmd = f'copy {filename} harddisk:/showtech location {dest}'
                copy2global = connection.send_command(copy_cmd, expect_string='sysadmin', max_loops=10000)
            except Exception as err:
                print('Some error occurred copying file to IOS-XR mode. Manual check required. Error: ', err)
                print(f'\n{100*"#"}\n')
            else:
                print(f'\n{copy2global}\n')
                connection.send_command('exit', expect_string='#')
                file_loc = filename.find('showtech-')
                filename = filename[file_loc:]
                filename = '/harddisk:/showtech/' + filename
                return filename


# This function is to Upload the file from Local machine/JumpServer to TAC case.
def upload_2_sr():
    for filename in local_files:
        try:
            print(f'\nUploading file -"{filename}" to TAC case')
            auth = HTTPBasicAuth(sr_username, sr_token)
            file_size = os.stat(filename).st_size
            with open(filename, "rb") as f:
                with tqdm(total=file_size, unit="KB", unit_scale=True, unit_divisor=1024) as t:
                    wrapped_file = CallbackIOWrapper(t.update, f, "read")
                    requests.put(url + filename, auth=auth, data=wrapped_file)
        except Exception as err:
            print(f'Some error occurred while uploading file - "{filename}" to TAC case', err)


prompt_choices = '''
#################################################################################################
# Author: Rakesh Kumar                                                                          #
# Version 1.0                                                                                   #
# Purpose: This Script can help Engineers/Customers to automate gathering TAC requested DATA    #
  for IOS-XR devices. The could include various show tech in IOS-XR/Admin mode or simple        #
  Show commands outputs.                                                                        #
                                                                                                #
  User need to supply the information to script based on Task chosen and this Script will       #
  generate the data and upload to TAC case.                                                     #
                                                                                                #
  Note: This script is designed for IOS-XR devices but user can tweak it for any platform.      #
                                                                                                #
#################################################################################################
==================================================================================
Please select the Task number from below List and Enter as your choice on Prompt.
==================================================================================
To run show tech commands in "IOS-XR mode" and upload file/s to TAC case Choose: 1
To run show tech commands in "Admin mode" and upload file/s to TAC case Choose:  2
To upload already generated or saved file/s to TAC case Choose:                  3
To run Only SHOW commands , capture output to file and upload it to TAC case Choose: 4
To upload existing file on Local machine/JumpHost to TAC case: 5
'''

print(prompt_choices)

get_choice = int(input('Enter your Choice: '))

# Get user input for TAC case details to upload files.
url = 'https://cxd.cisco.com/home/'
urllib3.disable_warnings()
sr_username = input("Enter SR number: ")
sr_token = input("Enter Upload Token: ")

# Defining Global variables.
device_ip = username = password = str()

# Capturing start time
start = time.perf_counter()

if get_choice < 5:
    # Take user input for Device IP and Credentials.
    device_ip = input('Enter device ip: ')
    username = input('Enter your username for device Login: ')
    password = getpass.getpass(prompt='Enter device Password: ')

local_files = []  # List to store file names on local machine/JumpServer.

# Device details dict for connecting to device.
device = {
    'device_type': 'cisco_xr',
    'host': device_ip,
    'username': username,
    'password': password,
    'port': 22,  # optional, default 22
    'verbose': True,  # optional, default False
    'global_delay_factor': 10,
}

# List to store any failed operation of command or file copy etc.
failed_list = []


if get_choice == 1:
    print(f'\nEnter one show tech command per line. Once all show tech commands entered,\n'
          f'just Hit Enter key to execute script\n')
    user_prompt = 'Enter show tech command(Only IOS-XR mode): '
    t = initial_func(user_prompt)
    (connection, prompt, hostname, lines) = t
    space_check()
    log_directory = create_local_dir()

    for user_cmd in lines:
        filename = run_cmd()
        if filename is None:
            failed_list.append(user_cmd)
            continue
        remote_md5 = remote_md5_check()
        local_file_name = retrieve_file('22')
        if local_file_name is None:
            failed_list.append(user_cmd)
            continue
        md5_local = local_md5_check()
        if md5_local is None:
            failed_list.append(user_cmd)
            continue
        md5_compare()

    print(f'List of local files: {local_files}\nLocation path for local files stored: {log_directory}\n')
    connection.disconnect()
    print(f'Disconnected from device - {hostname}')

    upload_2_sr()
    print(f'\n{20*"#"}\nList of failed commands, if any: {failed_list}')

elif get_choice == 2:
    print(f'\nEnter one Admin mode show tech command per line. Once all show tech commands entered,\n'
          f'just Hit Enter key to execute script\n')
    user_prompt = 'Enter command (ONLY admin mode commands without admin keyword): '
    t = initial_func(user_prompt)
    (connection, prompt, hostname, lines) = t
    space_check()
    log_directory = create_local_dir()

    loc_end = prompt.find(':')
    x = prompt[5:loc_end]
    if 'CPU' in x:
        dest = '0/' + x + '/VM1'
    else:
        dest = '0/' + x + '/CPU0/VM1'

    for user_cmd in lines:
        filename = run_cmd_admin()
        if filename is None:
            failed_list.append(user_cmd)
            continue
        file_md5 = remote_md5_check()
        remote_md5 = file_md5.strip()
        local_file_name = retrieve_file('22', )
        if local_file_name is None:
            failed_list.append(user_cmd)
            continue
        md5_local = local_md5_check()
        md5_local = md5_local.strip()
        if md5_local is None:
            failed_list.append(user_cmd)
            continue
        md5_compare()

    print(f'List of local files: {local_files}\nLocation path for local files stored: {log_directory}\n')
    connection.disconnect()
    print(f'Disconnected from device - {hostname}')

    upload_2_sr()
    print(f'\n{20*"#"}\nList of failed commands, if any: {failed_list}')

elif get_choice == 3:
    print(f'\nEnter filename with complete path on Device in each line. Once all files are entered,\n'
          f'just Hit Enter key to execute script\n')

    user_prompt = 'Enter filename with complete path: '
    t = initial_func(user_prompt)
    (connection, prompt, hostname, lines) = t
    log_directory = create_local_dir()

    for filename in lines:
        local_file_name = retrieve_file('22')
        if local_file_name is None:
            failed_list.append(filename)
            continue
        remote_md5 = remote_md5_check()
        md5_local = local_md5_check()
        if md5_local is None:
            failed_list.append(filename)
            continue
        md5_compare()

    print(f'List of local files: {local_files}\nLocation path for local files stored: {log_directory}\n')
    connection.disconnect()
    print(f'Disconnected from device - {hostname}')

    upload_2_sr()
    print(f'\n{20*"#"}\nList of failed files, if any: {failed_list}')

elif get_choice == 4:
    print(f'\nEnter Show command per line. Once all files are entered,\n'
          f'just Hit Enter key to execute script\n')

    user_prompt = 'Enter Show Command: '
    t = initial_func(user_prompt)
    (connection, prompt, hostname, lines) = t
    log_directory = create_local_dir()

    time_str = time.strftime("-%d%m%Y-%H%M%S-")
    log_filename = hostname + time_str + 'logs.txt'

    with open(log_filename, 'w') as logs:
        for cmd in lines:
            print(f'Now running command - {cmd}')
            output = connection.send_command(cmd, max_loops=50000, delay_factor=5, strip_command=False,
                                             strip_prompt=False)
            logs.write(f'{prompt}{output}\n{100 * "#"}\n')
            if '         ^' in output:
                failed_list.append(cmd)

    file = open(log_filename, "rb")
    data = file.read()
    bindata = bytearray(data)
    compressed_fname = log_filename + ".gz"
    with gzip.open(compressed_fname, "wb") as f:
        f.write(bindata)

    local_files.append(compressed_fname)
    print(f'File will be uploaded to case - {local_files}\nLocation path for local files stored: {log_directory}\n')
    connection.disconnect()
    print(f'Disconnected from device - {hostname}')

    upload_2_sr()
    print(f'\n{20*"#"}\nList of failed commands, if any. (Manual check of captured file required): {failed_list}')

elif get_choice == 5:
    print(f'\nEnter Local filename in each line. Once all files are entered,\n'
          f'just Hit Enter key to execute script\n')

    lines = []
    while True:
        line = input('Enter Local file name with Absolute path): ')

        if line:
            lines.append(line)
        else:
            break

    for x in lines:
        loc1 = x.rfind("/") + 1
        directory = x[:loc1]
        f_name = x[loc1:]

        os.chdir(directory)
        try:
            print(f'\nUploading file -"{f_name}" to TAC case')
            auth = HTTPBasicAuth(sr_username, sr_token)
            file_size = os.stat(f_name).st_size
            with open(f_name, "rb") as f:
                with tqdm(total=file_size, unit="KB", unit_scale=True, unit_divisor=1024) as t:
                    wrapped_file = CallbackIOWrapper(t.update, f, "read")
                    requests.put(url + f_name, auth=auth, data=wrapped_file)
        except Exception as err:
            print(f'Some error occurred while uploading file - "{f_name}" to TAC case', err)

else:
    print("Choose Option only from 1 to 5")

# Capturing Script end time.
end = time.perf_counter()
total_time = (end-start) / 60
print(f'\nTotal execution time {round(total_time,2)} minutes.')

print('\n\n#######  Thanks for using this Script.  ########\n')
import os
import paramiko
import oci
from oci.object_storage.models import PutObjectRequest

# OCI Configuration
config = oci.config.from_file()  # Assumes ~/.oci/config file
namespace = config["idnienhx4e48"]  # Object storage namespace
bucket_name = "Analytics_Bucket"
object_storage_client = oci.object_storage.ObjectStorageClient(config)

# SFTP Connection Details
SFTP_HOST = "aaocidisftpserver.sshocidiuser@aaocidisftpserver.blob.core.windows.net"
SFTP_PORT = 22
SFTP_USERNAME = "sshocidiuser"
SFTP_PASSWORD = "tZsVyW5iBAaHrjjz9h7ezjZgrkE7JkPt"
SFTP_DIRECTORY = "ocidi/"
LOCAL_TMP_DIR = "/tmp"

def get_sftp_file(sftp_host, sftp_port, sftp_username, sftp_password, sftp_directory, local_tmp_dir):
    # Initialize SFTP client and download file
    try:
        transport = paramiko.Transport((sftp_host, sftp_port))
        transport.connect(username=sftp_username, password=sftp_password)
        
        sftp = paramiko.SFTPClient.from_transport(transport)
        
        # Change to the correct directory on the SFTP server
        sftp.chdir(sftp_directory)
        
        # Get the list of files from the directory
        files = sftp.listdir()
        print(f"Files found in SFTP directory: {files}")
        
        for file_name in files:
            local_path = os.path.join(local_tmp_dir, file_name)
            sftp.get(file_name, local_path)  # Download file
            
            print(f"File downloaded: {local_path}")
        
        # Close the SFTP connection
        sftp.close()
        transport.close()

        return files
    
    except Exception as e:
        print(f"Error during SFTP download: {e}")
        return []

def upload_to_oci_object_storage(local_file_path, namespace, bucket_name, object_storage_client):
    # Upload downloaded file to OCI Object Storage
    try:
        with open(local_file_path, 'rb') as file:
            object_name = os.path.basename(local_file_path)
            put_object_request = PutObjectRequest(namespace_name=namespace,
                                                   bucket_name=bucket_name,
                                                   object_name=object_name,
                                                   put_object_body=file)
            response = object_storage_client.put_object(put_object_request)
            print(f"File uploaded to Object Storage: {response.data}")
    except Exception as e:
        print(f"Error uploading file to OCI Object Storage: {e}")

def oci_function_handler(ctx, data):
    # Step 1: Get files from SFTP
    sftp_files = get_sftp_file(SFTP_HOST, SFTP_PORT, SFTP_USERNAME, SFTP_PASSWORD, SFTP_DIRECTORY, LOCAL_TMP_DIR)
    
    # Step 2: Upload each file to OCI Object Storage
    for sftp_file in sftp_files:
        local_file_path = os.path.join(LOCAL_TMP_DIR, sftp_file)
        upload_to_oci_object_storage(local_file_path, namespace, bucket_name, object_storage_client)
        
    return "Files successfully uploaded to OCI Object Storage"

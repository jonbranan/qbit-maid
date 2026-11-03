import requests as r
from tomllib import load
import os

def apprise_notify(req_obj, host, port, aurls, title, body):
    payload = {'urls': aurls,'title': title,'body': body,}
    url = f'http://{host}:{port}/notify/'
    apprise_response = req_obj.post(url, json = payload ,verify=False)
    return apprise_response

class AppriseClient:
    def __init__(self):
        self.config = ''
        if os.environ.get("DOCKER"):
            self.host = os.environ["host"]
            self.port = os.environ["port"]
            self.aurls = os.environ["aurls"]
            self.title = os.environ["title"]
            self.body = os.environ["body"]
        if os.environ.get("toml_path"):
            config_file_path=os.environ["toml_path"]
            with open(config_file_path, 'rb') as c:
                self.config = load(c)
        if os.path.exists('./config.toml'):
            config_file_path = './config.toml'
            with open(config_file_path, 'rb') as c:
                self.config = load(c)
        if self.config:
            self.host = self.config["apprise"]["host"]
            self.port = self.config["apprise"]["port"]
            self.aurls = self.config["apprise"]["aurls"]
            self.title = self.config["apprise"]["title"]
            self.body = self.config["apprise"]["body"]
        self.apprise_response = apprise_notify(r,self.host,self.port,self.aurls,self.title,self.body)  

if __name__ == "__main__":
    AppriseClient()

import copy
import os
import random
import re
import secrets
import shutil
import string
import subprocess
import urllib.request
import webbrowser

import yaml

cloudflared_template = {
    "image": "cloudflare/cloudflared:latest",
    "restart": "unless-stopped",
    "command": "tunnel --url http://judge_backend:8080 --no-autoupdate run",
    "environment": [
        "TUNNEL_TOKEN="
    ],
    "depends_on": {
        "judge_backend": {
            "condition": "service_healthy"
        }
    }
}

cloudflared_cmd = ["docker", "run", "--rm", "-v", os.path.join(os.getcwd(), ".cloudflared")+":/home/nonroot/.cloudflared",
                   "cloudflare/cloudflared:latest"]


def get_tunnel_token() -> str:
    print("Try login to cloudflare...")
    proc = subprocess.Popen(cloudflared_cmd + ["login"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    login_url = None
    skip_login = False
    for line in proc.stdout:
        print(line.strip())
        if "existing certificate" in line:
            print("You have already logged in, skipping login")
            skip_login = True
            break
        match = re.search(r"(https://.+cloudflare.com.+)", line)
        if match:
            login_url = match.group(1)
            break
    if not skip_login:
        print("URL:", login_url)
        webbrowser.open(login_url)
        proc.wait()
        if proc.returncode != 0:
            print("Failed to login to cloudflare")
            return ""
    print("Login successful, getting tunnel token...")
    tunnel_name = "".join(random.choices(string.ascii_lowercase, k=10))
    tunnel_id = ""
    proc1 = subprocess.Popen(cloudflared_cmd + ["tunnel", "create", tunnel_name], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True)
    for line in proc1.stdout:
        print(line.strip())
        match = re.search(r"Created tunnel \w+ with id ([\w-]+)", line)
        if match:
            tunnel_id = match.group(1)
            break
    if not tunnel_id:
        print("Failed to get tunnel ID")
        return ""
    print("Tunnel ID:", repr(tunnel_id))
    dns_name = input("Enter the DNS name for the tunnel (e.g., example.com): ")
    if not dns_name:
        print("DNS name cannot be empty")
        return ""
    subprocess.run(cloudflared_cmd + ["tunnel", "route", "dns", tunnel_id, dns_name])
    proc2 = subprocess.Popen(cloudflared_cmd + ["tunnel", "token", tunnel_name], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True)
    token = ""
    for line in proc2.stdout:
        print(line.strip())
        if " " not in line.strip():
            token = line.strip()
            break
    if not token:
        print("Failed to get tunnel token")
        return ""
    print("Tunnel token:", repr(token))
    return token


def security_tools():
    while True:
        print("Choose a operation:")
        print("1. Go back")
        print("2. Remove exposed ports")
        print("3. Add cloudflare proxy (need tunnel token)")
        print("4. Add cloudflare proxy (auto create)")
        choice = input("Enter your choice: ")
        with open("docker-compose.yml", encoding="utf8") as f:
            info = yaml.load(f, Loader=yaml.FullLoader)
        if choice == "1":
            pass
        elif choice == "2":
            if not os.path.exists("docker-compose.yml"):
                print("docker-compose.yml not found.")
                break
            for service in info["services"]:
                if "judge_backend" != service and "ports" in info["services"][service]:
                    del info["services"][service]["ports"]
            print("Removed exposed ports from all services except judge_backend")
        elif choice == "3":
            token = input("Enter your cloudflare tunnel token: ")
            template = copy.deepcopy(cloudflared_template)
            template["environment"][0] = f"TUNNEL_TOKEN={token}"
            info["services"]["cloudflare"] = template
            if "ports" in info["services"]["judge_backend"]:
                del info["services"]["judge_backend"]["ports"]
            print("Added cloudflare proxy service to docker-compose.yml")
        elif choice == "4":
            token = get_tunnel_token()
            if not token:
                print("Failed to get tunnel token, please try again")
                continue
            template = copy.deepcopy(cloudflared_template)
            template["environment"][0] = f"TUNNEL_TOKEN={token}"
            info["services"]["cloudflare"] = template
            if "ports" in info["services"]["judge_backend"]:
                del info["services"]["judge_backend"]["ports"]
            print("Added cloudflare proxy service to docker-compose.yml")
        else:
            print("Invalid choice, please try again")
            continue
        with open("docker-compose.yml", "w", encoding="utf8") as f:
            yaml.dump(info, f)
        break


def main():
    if not os.path.exists("docker-compose.yml"):
        dc_url = "https://raw.githubusercontent.com/LittleOrange666/OrangeJudge/refs/heads/main/docker-compose.yml"
        try:
            with urllib.request.urlopen(dc_url) as response:
                if response.status != 200:
                    print("Failed to download docker-compose.yml")
                    return
                dc_text = response.read().decode("utf-8")
                info = yaml.load(dc_text, Loader=yaml.FullLoader)
        except Exception as e:
            print(f"Error occurred: {e}")
            return

        def upd(s, k, v):
            if "environment" not in info["services"][s]:
                info["services"][s]["environment"] = []
            l = info["services"][s]["environment"]
            for i in range(len(l)):
                if l[i].startswith(k + "="):
                    l[i] = k + "=" + v
                    return
            l.append(k + "=" + v)

        judge_token = secrets.token_hex(33)
        upd("judge_server", "JUDGE_TOKEN", judge_token)
        upd("judge_backend", "JUDGE_TOKEN", judge_token)
        db_password = secrets.token_hex(21)
        upd("judge_mariadb", "MYSQL_PASSWORD", db_password)
        upd("judge_mariadb", "MYSQL_ROOT_PASSWORD", secrets.token_hex(21))
        upd("judge_backend", "MYSQL_PASSWORD", db_password)
        flask_secret_key = secrets.token_hex(21)
        upd("judge_backend", "FLASK_SECRET_KEY", flask_secret_key)
        with open("docker-compose.yml", "w", encoding="utf8") as f:
            yaml.dump(info, f)
        print("Download docker-compose.yml successfully")
    else:
        print("docker-compose.yml already exists, skipping download")
    if not os.path.exists("OrangeJudgeLangs"):
        os.system("git clone https://github.com/LittleOrange666/OrangeJudgeLangs.git")
        if not os.path.exists("OrangeJudgeLangs"):
            print("Failed to clone OrangeJudgeLangs repository")
            return
        shutil.copytree("OrangeJudgeLangs/langs", "./langs", dirs_exist_ok=True)
        print("Clone OrangeJudgeLangs repository successfully")
    langs = [f[:-3] for f in os.listdir("OrangeJudgeLangs") if f.endswith(".py") and f != "tools.py"]
    while True:
        print("Choose a operation:")
        print("1. Quit")
        print("2. start judge")
        print("3. security tools")
        for i, lang in enumerate(langs):
            print(f"{i + 4}. install {lang}")
        choice = input("Enter your choice: ")
        if choice == "1":
            break
        elif choice == "2":
            os.system("docker-compose up -d")
            print("Judge server started")
        elif choice == "3":
            security_tools()
        elif choice.isdigit() and 4 <= int(choice) <= len(langs) + 3:
            lang = langs[int(choice) - 4]
            os.system(f"python3 OrangeJudgeLangs/{lang}.py")
        else:
            print("Invalid choice, please try again")


if __name__ == "__main__":
    main()

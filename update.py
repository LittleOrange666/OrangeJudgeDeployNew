import os

import requests
import yaml


def query(username: str, image_name: str):
    url = f"https://registry.hub.docker.com/v2/repositories/{username}/{image_name}/tags/?page_size=5"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        tags = [tag['name'] for tag in data.get('results', []) if tag["name"] != "latest"]
        return tags[0]
    else:
        raise Exception(f"Failed to fetch tags for {username}/{image_name}. Status code: {response.status_code}")


def main():
    if not os.path.exists("docker-compose.yml"):
        print("docker-compose.yml not found.")
        return
    username = "littleorange666"
    image_name1 = "orange_judge"
    image_name2 = "judge_server"
    version1 = query(username, image_name1)
    version2 = query(username, image_name2)
    with open("docker-compose.yml", encoding="utf8") as f:
        info = yaml.load(f, Loader=yaml.FullLoader)
    cur_version1 = info["services"]["judge_backend"]["image"].split(":")[-1]
    cur_version2 = info["services"]["judge_server"]["image"].split(":")[-1]
    print("For judge_backend, current version is", cur_version1, "and latest version is", version1)
    print("For judge_server, current version is", cur_version2, "and latest version is", version2)
    if cur_version1 == version1 and cur_version2 == version2:
        print("You are using the latest version.")
        return
    print("You are not using the latest version, updating...")
    info["services"]["judge_backend"]["image"] = f"{username}/{image_name1}:{version1}"
    info["services"]["judge_server"]["image"] = f"{username}/{image_name2}:{version2}"
    environments = {o.split("=")[0]:o.split("=")[1] for o in info["services"]["judge_backend"]["environment"]}
    environments["ORANGEJUDGE_VERSION"] = version1
    info["services"]["judge_backend"]["environment"] = [f"{k}={v}" for k, v in environments.items()]
    with open("docker-compose.yml", "w", encoding="utf8") as f:
        yaml.dump(info, f)
    print("Updated docker-compose.yml with the latest version.")
    os.system("docker compose up -d")



if __name__ == "__main__":
    main()

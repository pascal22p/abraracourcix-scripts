#!/usr/bin/env python3

import docker
import sys
import socket
import dateutil.parser
import traceback
import argparse
import logging

appName = "docker-stats"

try:
    from systemd.journal import JournalHandler
    logger = logging.getLogger(appName)
    logger.addHandler(JournalHandler(SYSLOG_IDENTIFIER=appName))
except ImportError:
    logger = logging.getLogger(appName)
    stdout = logging.StreamHandler(sys.stdout)
    logger.addHandler(stdout)
finally:
    logger.setLevel(logging.INFO)

def docker_stats(prefix, docker_path):
    try:
        client = docker.DockerClient(base_url="unix:/%s"%docker_path)
    except Exception as e:
        logger.error("Could not connect to docker (%s)"%e)
        sys.exit(2)

    try:
        sock = socket.socket()
        sock.connect(("localhost", 2003))
    except Exception as e:
        logger.error("Could not connect to socket (%s)"%e)
        sys.exit(2)

    containers = client.containers.list()

    for container in containers:
        stats = container.stats(stream=False)
        timestamp = dateutil.parser.isoparse(stats['read']).timestamp()

        name = stats['name'].lstrip('/').rstrip('/').replace('.', '-')

        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
        system_cpu_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
        number_cpus = stats['cpu_stats']['online_cpus']
        cpu_usage = (cpu_delta / system_cpu_delta) * number_cpus * 100.0

        used_memory = stats['memory_stats']['usage'] - stats['memory_stats']['stats']['cache']
        available_memory = stats['memory_stats']['limit']
        memory_usage = (used_memory / available_memory) * 100.0

        message = '%s.docker.%s.cpu_usage %f %d\n' % (prefix, name, cpu_usage, timestamp)
        message += '%s.docker.%s.memory_usage %f %d\n' % (prefix, name, memory_usage, timestamp)
        message += '%s.docker.%s.memory_used %d %d\n' % (prefix, name, used_memory, timestamp)
        message += '%s.docker.%s.memory_available %d %d\n' % (prefix, name, available_memory, timestamp)

        sock.sendall(message.encode())

    sock.close()

def main():
    parser = argparse.ArgumentParser(description='Create a snapshot of the vps')
    parser.add_argument('--prefix', metavar='PREFIX', required=True,
                        help='graphite prefix')
    parser.add_argument('--docker', metavar='DOCKER', required=True,
                        help='docker socket path')
    args = parser.parse_args()

    docker_stats(args.prefix, args.docker)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error('An unexpected error occurred')
        logger.error("".join(traceback.format_exception(None,e, e.__traceback__)).replace("\n",""))
        sys.exit(2)

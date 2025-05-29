"""This module contains functionality to easily interact with the network packet interceptor subprocess."""
import subprocess
import traceback
from subprocess import PIPE, Popen, TimeoutExpired
from sys import platform
from threading import Thread

import docker
from docker import DockerClient
from loguru import logger


def cleanup_docker_containers(hostname_prefix: str):
    try:
        all_containers = subprocess.run(
            ["docker", "container", "ls", "-q", "-a"],
            capture_output=True, text=True).stdout.strip().splitlines()
        containers = [c for c in all_containers if c.startswith(f"{hostname_prefix}_validator")]
        if containers:
            subprocess.run(["docker", "container", "stop"] + containers, check=True)

        all_volumes = subprocess.run(["docker", "volume", "ls", "-q"], capture_output=True,
                                     text=True).stdout.strip().splitlines()
        volumes = [v for v in all_volumes if v.startswith(f"{hostname_prefix}_validator")]
        if volumes:
            subprocess.run(["docker", "volume", "rm"] + volumes, check=True)
    except Exception as e:
        logger.warning(f"Error cleaning up docker containers: {e}")


class InterceptorManager:
    """Class for interacting with the network packet interceptor subprocess."""

    def __init__(self):
        """Initialize the InterceptorManager, with None for the process variable."""
        self.process: Popen | None = None

    @staticmethod
    def __check_output(proc: Popen):
        """Log the stdout and stderr of the subprocess."""
        stdout, stderr = proc.communicate()
        if stdout:
            logger.debug(f"\n{stdout}")
        if stderr:
            logger.debug(f"\n{stderr}")


    def start_new(self):
        """Starts the rocket-interceptor subprocess, and spawns a thread checking for output."""
        file = (
            "rocket-interceptor"
            if platform != "win32"
            else "/rocket_interceptor/rocket-interceptor.exe"
        )
        logger.info("Starting interceptor")
        try:
            self.process = Popen(
                [f"./{file}"],
                cwd="./rocket_interceptor",
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            logger.error(
                "Could not find the rocket-interceptor executable. Did you build the interceptor?"
            )
            traceback.print_exception(exc)
            exit(2)

        t = Thread(target=self.__check_output, args=[self.process])
        t.start()

    def restart(self):
        """Stops and starts the rocket-interceptor subprocess."""
        self.stop()
        self.start_new()

    def stop(self):
        """Stops the rocket-interceptor subprocess."""
        # Check if this is the end of an active run
        if self.process:
            logger.info("Stopping interceptor")
            self.process.terminate()
            try:
                self.process.wait(timeout=5.0)
            except TimeoutExpired:
                self.process.kill()

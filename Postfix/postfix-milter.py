#!/usr/bin/env python3
"""
postfix_milter.py - A simple Python milter that accepts all messages without modification
Logs to systemd journal (journald)
"""

import Milter
import sys
import os
import time
import socket
from systemd import journal
import sys

class PostfixMilter(Milter.Base):
    """Simple milter that passes all messages unchanged and logs to journald"""

    def __init__(self, email_address_to_filter):
        self.id = "unknown"  # Message ID
        self.mail_from = None
        self.hostname = "unknown"
        self.hostaddr = None
        self.email_address_to_filter = email_address_to_filter

    def connect(self, hostname, family, hostaddr):
        """Record connection from client"""
        self.hostname = hostname
        self.hostaddr = hostaddr
        journal.send(f"Connection from {hostname} [{hostaddr}]",
                    PRIORITY=journal.LOG_INFO,
                    SYSLOG_IDENTIFIER="postfix-milter",
                    HOSTNAME=socket.gethostname(),
                    CLIENT_HOSTNAME=hostname,
                    CLIENT_IP=str(hostaddr))
        return Milter.CONTINUE

    def hello(self, heloname):
        """Record HELO/EHLO command"""
        journal.send(f"HELO/EHLO from {heloname}",
                    PRIORITY=journal.LOG_INFO,
                    SYSLOG_IDENTIFIER="postfix-milter",
                    CLIENT_HOSTNAME=self.hostname,
                    HELO_NAME=heloname)
        return Milter.CONTINUE

    def envfrom(self, mailfrom, *args):
        """Record MAIL FROM command"""
        self.mail_from = mailfrom
        journal.send(f"MAIL FROM: {mailfrom}",
                    PRIORITY=journal.LOG_INFO,
                    SYSLOG_IDENTIFIER="postfix-milter",
                    CLIENT_HOSTNAME=self.hostname,
                    MAIL_FROM=mailfrom)
        return Milter.CONTINUE

    def envrcpt(self, to, *args):
        """Record RCPT TO command and reject non-parois.net destinations for authenticated users"""
        auth_authen = self.getsymval("{auth_authen}")
        rcpt_to = self.getsymval("{rcpt_host}")

        if auth_authen:
            journal.send(f"Authenticated user: {auth_authen}",
                    PRIORITY=journal.LOG_INFO,
                    SYSLOG_IDENTIFIER="postfix-milter")

            if auth_authen.lower() == self.email_address_to_filter:
                if rcpt_to != "parois.net":
                    journal.send(f"Authenticated user {auth_authen} attempted to send to unauthorized recipient {to}",
                        PRIORITY=journal.LOG_ERR,
                        SYSLOG_IDENTIFIER="postfix-milter",
                        CLIENT_HOSTNAME=self.hostname,
                        MAIL_FROM=self.mail_from,
                        AUTH_USER=auth_authen,
                        REJECTED_RCPT=rcpt_to)
                    return Milter.REJECT


        journal.send(f"RCPT TO: {to}",
                PRIORITY=journal.LOG_INFO,
                SYSLOG_IDENTIFIER="postfix-milter",
                CLIENT_HOSTNAME=self.hostname,
                RCPT_TO=to)
        return Milter.CONTINUE

    def header(self, name, value):
        """Record message header"""
        if name.lower() == "message-id":
            self.id = value
            journal.send(f"Message ID: {value}",
                        PRIORITY=journal.LOG_INFO,
                        SYSLOG_IDENTIFIER="postfix-milter",
                        CLIENT_HOSTNAME=self.hostname,
                        MESSAGE_ID=value)
        return Milter.CONTINUE

    def eoh(self):
        """End of headers"""
        return Milter.CONTINUE

    def body(self, chunk):
        """Process message body chunk - we don't even look at it"""
        return Milter.CONTINUE

    def eom(self):
        """End of message - decide header injection based on authenticated user"""
        filtered_value = "No"  # Default

        # Check if this is an authenticated session with a known user
        auth_authen = self.getsymval("{auth_authen}")
        if auth_authen:
            journal.send(f"Authenticated user: {auth_authen}",
                    PRIORITY=journal.LOG_INFO,
                    SYSLOG_IDENTIFIER="postfix-milter")

            if auth_authen.lower() == self.email_address_to_filter:
                filtered_value = "Yes"

        # Add header
        self.addheader("X-Filtered", filtered_value)

        journal.send(f"Message {self.id} from {self.mail_from} accepted with X-Filtered: {filtered_value}",
                PRIORITY=journal.LOG_INFO,
                SYSLOG_IDENTIFIER="postfix-milter",
                CLIENT_HOSTNAME=self.hostname,
                MESSAGE_ID=self.id,
                MAIL_FROM=self.mail_from,
                FILTERED=filtered_value,
                STATUS="accepted")

        return Milter.ACCEPT

    def abort(self):
        """Client disconnected prematurely"""
        journal.send("Client disconnected prematurely",
                    PRIORITY=journal.LOG_WARNING,
                    SYSLOG_IDENTIFIER="postfix-milter",
                    CLIENT_HOSTNAME=self.hostname)
        return Milter.ACCEPT

    def close(self):
        """Client disconnected normally"""
        journal.send("Connection closed",
                    PRIORITY=journal.LOG_INFO,
                    SYSLOG_IDENTIFIER="postfix-milter",
                    CLIENT_HOSTNAME=self.hostname)
        return Milter.ACCEPT

def main():
    """Main function to run the milter"""
    # Socket path where the milter will listen
    socket_path = "/var/spool/postfix/milter/postfix_milter.sock"
    socket_dir = os.path.dirname(socket_path)

    email_address_to_filter = sys.argv[1]

    # Make sure the directory exists
    if not os.path.exists(socket_dir):
        journal.send(f"Creating socket directory: {socket_dir}",
                    PRIORITY=journal.LOG_INFO,
                    SYSLOG_IDENTIFIER="postfix-milter")
        os.makedirs(socket_dir, exist_ok=True)

    # Remove socket if it already exists
    if os.path.exists(socket_path):
        journal.send(f"Removing existing socket: {socket_path}",
                    PRIORITY=journal.LOG_INFO,
                    SYSLOG_IDENTIFIER="postfix-milter")
        os.unlink(socket_path)

    # Register to socket and run
    Milter.factory = lambda: PostfixMilter(email_address_to_filter)

    # We don't need any modification flags since we're just passing through
    Milter.set_flags(0)

    journal.send(f"Starting postfix milter on {socket_path} for user {email_address_to_filter}",
                PRIORITY=journal.LOG_INFO,
                SYSLOG_IDENTIFIER="postfix-milter",
                SOCKET_PATH=socket_path)
    Milter.runmilter("postfix_milter", socket_path, 240)
    journal.send("Milter finished",
                PRIORITY=journal.LOG_INFO,
                SYSLOG_IDENTIFIER="postfix-milter")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        journal.send("Milter stopped by user",
                    PRIORITY=journal.LOG_INFO,
                    SYSLOG_IDENTIFIER="postfix-milter")
    except Exception as e:
        journal.send(f"Error in milter: {str(e)}",
                    PRIORITY=journal.LOG_ERR,
                    SYSLOG_IDENTIFIER="postfix-milter",
                    EXCEPTION=str(e))

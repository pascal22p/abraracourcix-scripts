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
from email.message import EmailMessage
import smtplib

class PostfixMilter(Milter.Base):
    """Simple milter that passes all messages unchanged and logs to journald"""

    def extract_ip(self, hostaddr):
        if isinstance(hostaddr, tuple):
            return hostaddr[0]
        else:
            return str(hostaddr)

    def __init__(self, email_address_to_filter, admin_email_address):
        self.id = "unknown"  # Message ID
        self.mail_from = None
        self.hostname = "unknown"
        self.hostaddr = None
        self.email_address_to_filter = email_address_to_filter
        self.admin_email_address = admin_email_address

    def connect(self, hostname, family, hostaddr):
        """Record connection from client"""
        self.hostname = hostname
        self.hostaddr = hostaddr
        journal.send(f"Connection from {hostname} [{hostaddr}]",
                    PRIORITY=journal.LOG_INFO,
                    SYSLOG_IDENTIFIER="postfix-milter",
                    HOSTNAME=socket.gethostname(),
                    CLIENT_HOSTNAME=hostname,
                    CLIENT_IP=self.extract_ip(hostaddr))
        return Milter.CONTINUE

    def hello(self, heloname):
        """Record HELO/EHLO command"""
        journal.send(f"HELO/EHLO from {heloname}",
                    PRIORITY=journal.LOG_INFO,
                    SYSLOG_IDENTIFIER="postfix-milter",
                    CLIENT_HOSTNAME=str(self.hostname),
                    HELO_NAME=str(heloname))
        return Milter.CONTINUE

    def envfrom(self, mailfrom, *args):
        """Record MAIL FROM command"""
        self.mail_from = mailfrom
        journal.send(f"MAIL FROM: {mailfrom}",
                    PRIORITY=journal.LOG_INFO,
                    SYSLOG_IDENTIFIER="postfix-milter",
                    CLIENT_HOSTNAME=str(self.hostname),
                    MAIL_FROM=str(mailfrom))
        return Milter.CONTINUE

    def envrcpt(self, to, *args):
        """Record RCPT TO command and reject non-parois.net destinations for authenticated users"""
        auth_authen = self.getsymval("{auth_authen}")
        rcpt_to = self.getsymval("{rcpt_host}")
        mail_addr = self.getsymval("{mail_addr}")
        rcpt_addr = self.getsymval("{rcpt_addr}")

        if auth_authen:
            journal.send(f"Authenticated user: {auth_authen}",
                    PRIORITY=journal.LOG_INFO,
                    SYSLOG_IDENTIFIER="postfix-milter")

            if auth_authen.lower() == self.email_address_to_filter:
                if rcpt_to != "parois.net":
                    message = EmailMessage()
                    message.add_header("X-Original-Recipient", rcpt_addr)
                    message.add_header("X-Filtered-Reason", "Blocked non-parois.net recipient")
                    message.add_header("X-Original-Sender", mail_addr)
                    message.add_header("Subject", f"Blocked message from {mail_addr} to {rcpt_addr}")
                    message.set_content(f"Blocked message from {mail_addr} to {rcpt_addr}")

                    try:
                        with smtplib.SMTP("localhost") as smtp:
                            smtp.send_message(message, from_addr=mail_addr, to_addrs=admin_email_address)

                        journal.send(f"Blocked message from {self.mail_from} forwarded to {admin_email_address}",
                                     PRIORITY=journal.LOG_INFO,
                                     SYSLOG_IDENTIFIER="postfix-milter",
                                     MESSAGE_ID=str(self.id))
                    except Exception as e:
                        journal.send(f"Failed to forward blocked email: {e}",
                                     PRIORITY=journal.LOG_ERR,
                                     SYSLOG_IDENTIFIER="postfix-milter",
                                     EXCEPTION=str(e))

                    journal.send(f"Authenticated user {auth_authen} attempted to send to unauthorized recipient {to}",
                        PRIORITY=journal.LOG_ERR,
                        SYSLOG_IDENTIFIER="postfix-milter",
                        CLIENT_HOSTNAME=str(self.hostname),
                        MAIL_FROM=str(self.mail_from),
                        AUTH_USER=str(auth_authen),
                        REJECTED_RCPT=str(rcpt_to))
                    return Milter.REJECT


        journal.send(f"RCPT TO: {to}",
                PRIORITY=journal.LOG_INFO,
                SYSLOG_IDENTIFIER="postfix-milter",
                CLIENT_HOSTNAME=str(self.hostname),
                RCPT_TO=str(to))
        return Milter.CONTINUE

    def header(self, name, value):
        """Record message header"""
        if name.lower() == "message-id":
            self.id = value
            journal.send(f"Message ID: {value}",
                        PRIORITY=journal.LOG_INFO,
                        SYSLOG_IDENTIFIER="postfix-milter",
                        CLIENT_HOSTNAME=str(self.hostname),
                        MESSAGE_ID=str(value))
        return Milter.CONTINUE

    def eoh(self):
        """End of headers"""
        return Milter.CONTINUE

    def body(self, chunk):
        """Process message body chunk"""
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
                CLIENT_HOSTNAME=str(self.hostname),
                MESSAGE_ID=str(self.id),
                MAIL_FROM=str(self.mail_from),
                FILTERED=str(filtered_value),
                STATUS="accepted")

        return Milter.ACCEPT

    def abort(self):
        """Client disconnected prematurely"""
        journal.send("Client disconnected prematurely",
                    PRIORITY=journal.LOG_WARNING,
                    SYSLOG_IDENTIFIER="postfix-milter",
                    CLIENT_HOSTNAME=str(self.hostname))
        return Milter.ACCEPT

    def close(self):
        """Client disconnected normally"""
        journal.send("Connection closed",
                    PRIORITY=journal.LOG_INFO,
                    SYSLOG_IDENTIFIER="postfix-milter",
                    CLIENT_HOSTNAME=str(self.hostname))
        return Milter.ACCEPT

def main():
    """Main function to run the milter"""
    # Socket path where the milter will listen
    socket_path = "/var/spool/postfix/milter/postfix_milter.sock"
    socket_dir = os.path.dirname(socket_path)

    email_address_to_filter = sys.argv[1]
    admin_email_address = sys.argv[2]

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
    Milter.factory = lambda: PostfixMilter(email_address_to_filter, admin_email_address)

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

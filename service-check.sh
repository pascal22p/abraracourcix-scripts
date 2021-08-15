#!/bin/bash
lookAt="amavisd collectd docker dovecot fail2ban firewalld mariadb nginx ntpd opendmarc php-fpm postfix seafile seahub spamassassin"

for service in $lookAt; do
    result=`systemctl is-active $service`
    if [[ $result != "active" ]]; then
        systemd-cat -t service-check -p err echo "$service is not running"
    fi
done


# Bootstrap Ansible CGI

This repository contains a CGI script to generate kickstart, preseed,
yast or any other config file or script to fully automate the
installation with the availability of the ansible inventory and
additional "secret" facts. I've used the same technologies and design
principles Ansible uses, mainly for convenience.

And there is another CGI script which triggers git pull's if
repositories (bootstrap or inventory) change.

**Note:** Commits to the MASTER branch go to production immediately!

## Variables

### Sources (in order of precedence from weakest to strongest):

- inventory (*ALL*)
- webserver (os_name, os_version, filename, hostname)
- vars_files (*ALL*, in order mentioned above)
- script (template, vars_files, template_files, date, time)

### Availability:

- inside templates:        inventory, webserver, vars_files, script
- cgi.yml: template_files: inventory, webserver, vars_files
- cgi.yml: vars_files:     inventory, webserver

Formatting: http://jinja.pocoo.org/docs/2.10/

## Setup

The server requires python with yaml and jinja2 and ansible-inventory
(usually the ansible-package in a distro should be enough).

### Webserver

The webserver must be configured to allow cgi-script execution and
following symlinks. Then, a simple symlink to cgi.py named
"bootstrap" is enough. This leads to the following URL structure:

    https://SERVER/bootstrap/os_name/os_version/filename

### Git Hook

Same applies here (a symlink to pull.py as "git-pull").

URL structure:

    https://SERVER/git-pull/repo_name

Make sure to have the repos configured in pull.yml initially cloned
and to allow the webserver user to pull them without interaction
(like a password prompt). Then configure the git-server to request
a HTTP GET to the URL above on every push.

### Booting

Make sure to boot the operating system installer pointing to the
respective URL, in pxelinux, this could look like:

    APPEND initrd=ubuntu-cosmic-amd64-initrd.gz priority=critical auto=true url=https://SERVER/bootstrap/ubuntu/cosmic/preseed.cfg
    KERNEL ubuntu-cosmic-amd64-linux

    APPEND initrd=rhel-7-x86_64-initrd.img text ks=https://SERVER/bootstrap/rhel/7/kickstart.cfg
    KERNEL rhel-7-x86_64-vmlinuz


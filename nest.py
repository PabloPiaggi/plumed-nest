#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function

import yaml
import sys
import re
import urllib.request
import zipfile
from contextlib import contextmanager
import os
import pathlib
import subprocess

def get_publication(doi):
    # check if unpublished
    if(doi=="unpublished"): return doi
    # retrieve citation
    cit = subprocess.check_output('curl -LH "Accept: text/bibliography; style=science" http://dx.doi.org/'+doi, shell=True).decode('utf-8').strip()
    if("DOI Not Found" in cit):
      pub="DOI not found. Check the provided DOI!"
    else:
      pub="["+cit[3:len(cit)]+"](https://doi.org/"+doi+")"
    return pub
 
def get_short_name(lname, length):
    if(len(lname)>length): sname = lname[0:length]+"..."
    else: sname = lname
    return sname

def plumed_format(source):
    suffix="md"
    # list of generated files, returned
    lista=[]
    with open(source) as f:
        destination=source + "." + suffix
        lista.append(destination)
        with open(destination,"w") as o:
            lines = f.read().splitlines()
            continuation=False
            comment=False
            action=""
            endplumed=False
            action_next_line=False
            print("Source: " + source,file=o)
            # make sure Jekyll does not interfere with format
            # <pre> marks a preformatted block
            print("{% raw %}<pre>",file=o)
            for line in lines:
                words=re.sub("#.*","",line).split()
                if endplumed:
                    line="<span style=\"color:blue\">" + line + "</span>"
                else:
                    if continuation:
                        if len(words)>0:
                            if words[0]=="...":
                                # end of continuation
                                continuation=False
                            if action_next_line:
                                # action was not in first line, thus it is here
                                action=words[0]
                                action_next_line=False
                    else:
                        action=""
                        action_next_line=False
                        if len(words)>0:
                            if len(words)>1 and words[-1]=="...":
                                # first line of multiline action:
                                continuation=True
                                if re.match("^.*:$",words[0]):
                                    if len(words)>2:
                                        # first word is the label
                                        action=words[1]
                                    else:
                                        # first word of next nonempty line will be the action
                                        action_next_line=True
                                else:
                                    action=words[0]
                            else:
                                # single line action, easy to parse:
                                if re.match("^.*:$",words[0]):
                                    action=words[1]
                                else:
                                    action=words[0]
                    if len(action)>0:
                        und_action = ''
                        for ch in action:
                            und_action = und_action + '_' + ch
                        action_url="<a href=\"" + "https://plumed.github.io/doc-master/user-doc/html/" + re.sub('___+', '__', und_action.lower()) + ".html\">" + action + "</a>"
                        line=re.sub(action,action_url,line)
                    
                    if action=="ENDPLUMED":
                        endplumed=True
                    
                    if action=="INCLUDE":
                        # for now only oneline INCLUDE statements are supported. Could be extended later
                        if len(words)>1 and re.match("^FILE=.*",words[1]):
                            file=re.sub("^FILE=","",words[1])
                            try:
                                lista+=plumed_format(str(pathlib.PurePosixPath(source).parent)+"/"+file)
                                # we here link with html suffix (even if we generated md files) otherwise links to do work after rendering
                                file_url="<a href=\"" + file + ".html\">" + file + "</a>" 
                                line=re.sub(" FILE=[^ ]*"," FILE=" + file_url,line)
                            except FileNotFoundError:
                                # if file is not found, do not replace the link and do not append lista
                                pass
                            
                # mark comments as such
                line=re.sub("(#.*$)","<span style=\"color:blue\">\\1</span>",line)    
                print(line,file=o)
                
            print("</pre>{% endraw %}",file=o)
            # convert to set to remove duplicates
            return list(set(lista))


def plumed_input_test(exe,source):
    cwd = os.getcwd()
    run_folder = str(pathlib.PurePosixPath(source).parent)
    plumed_file = os.path.basename(source)
    with cd(run_folder):
        child = subprocess.Popen(['mpiexec', '-np', '2', exe, 'driver', '--natoms', '100000', '--parse-only', '--kt', '2.49', '--plumed', plumed_file, '--multi', '2'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout,stderr = child.communicate()
        rc = child.returncode
    with cd(cwd):
        return rc

def add_readme(file, version, tested, success):
    with open("README.md","a") as o:
        badge = ''
        for i in range(len(tested)):
            if success[i]==0: 
                badge = badge + ' [![tested on ' + tested[i] + '](https://img.shields.io/badge/' + tested[i] + '-' + 'passing' + '-green.svg)](https://github.com/plumed/plumed2/tree/' + tested[i] + ')'
            else:
                badge = badge + ' [![tested on ' + tested[i] + '](https://img.shields.io/badge/' + tested[i] + '-' + 'failed' + '-red.svg)](https://github.com/plumed/plumed2/tree/' + tested[i] + ')'
        print("| [" + file + "](./"+file+".md"+") | " + version +" | " + badge + " |" + "  ", file=o)


@contextmanager
def cd(newdir):
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)

with open("_data/eggs.yml","w") as o:
    print("# file containing egg database.",file=o)

# list of paths - not ordered
pathlist=list(pathlib.Path('.').glob('eggs*/*/nest.yml'))
# cycle on ordered list
for path in sorted(pathlist, reverse=True, key=lambda m: str(m)):

    path=re.sub("nest.yml$","",str(path))

    with cd(path):

        stram = open("nest.yml", "r")
        config=yaml.load(stram,Loader=yaml.BaseLoader)
        # check fields
        for field in ("url","pname","category","keyw","version","contributor","doi","date"):
            if not field in config:
               raise RuntimeError(field+" not found")
        print(config)

        if re.match("^.*\.zip$",config["url"]):
            urllib.request.urlretrieve(config["url"], 'file.zip')
            zf = zipfile.ZipFile("file.zip", "r")
            root=zf.namelist()[0]
            zf.extractall()
        else:
            raise RuntimeError("cannot interpret url " + config["url"])

        if not "plumed_input" in config:
            config["plumed_input"]=sorted(pathlib.Path('.').glob('**/plumed*.dat'))
            config["plumed_input"]=[str(v) for v in config["plumed_input"]]
        else:
            config["plumed_input"]=[root+"/"+str(v) for v in config["plumed_input"]]
        print(config)

        egg_id=path[5:7] + "." + path[8:11]

        with open("README.md","w") as o:
            print("**Project ID:** ", "plumeDnest:" + egg_id +"  ", file=o)
            print("**Name:** ",config["pname"]+"  ", file=o)
            print("**Archive:** [",config["url"]+"]("+config["url"]+")  ", file=o)
            print("**Category:** ",config["category"]+"  ", file=o)
            print("**Keywords:** ",config["keyw"]+"  ", file=o)
            print("**PLUMED version:** ",config["version"]+"  ", file=o)
            print("**Contributor:** ",config["contributor"]+"  ", file=o)
            pub = get_publication(config["doi"]) 
            print("**Publication:** " + pub + "  ", file=o)
            print("**Submission date:** ",config["date"]+"  ", file=o)
            print("**PLUMED input files:**  ", file=o)
            print("  ", file=o)
            print("| File     | Declared compatibility | Compatible with |  ", file=o) 
            print("|:--------:|:---------:|:--------:|  ", file=o)

        for file in config["plumed_input"]:
# in principle returns the list of produced files, not used yet:
            plumed_format(file)
            success=plumed_input_test("plumed",file)
            success_master=plumed_input_test("plumed_master",file)
            add_readme(file, str(config["version"]) , (os.environ["PLUMED_LATEST_VERSION"],"master"), (success,success_master))

        # print instructions, if present
        with open("README.md","a") as o:
             print("  ", file=o)
             print("**Project description and instructions**  ", file=o)
             try:
               print(config["instructions"], file=o)
             except KeyError:
               print("*Description and instructions not provided*  ",file=o)

        with open("../../_data/eggs.yml","a") as o:
# quote around id is required otherwise Jekyll thinks it is a number
            print("- id: '" + egg_id + "'",file=o)
            print("  name: " + config["pname"],file=o)
            print("  shortname: " + get_short_name(config["pname"],15),file=o)
            print("  category: " + config["category"],file=o)
            print("  keywords: " + config["keyw"],file=o)
            print("  shortkeywords: " + get_short_name(config["keyw"],25),file=o)
            print("  contributor: " + config["contributor"],file=o)
            print("  doi: " + config["doi"],file=o)
            print("  shortdoi: " + get_short_name(config["doi"],15),file=o)
            print("  path: " + path,file=o)


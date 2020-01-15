FROM jupyter/minimal-notebook

USER jovyan

RUN conda create -y -n env_py2 anaconda python=2.7

RUN conda install nb_conda_kernels -y

ADD ./plapi-20.30.0py2-py2.7-linux-x86_64.egg /tmp/plapi-20.30.0py2-py2.7-linux-x86_64.egg

RUN conda run -n env_py2 easy_install /tmp/plapi-20.30.0py2-py2.7-linux-x86_64.egg

RUN mkdir /home/jovyan/work -p

RUN chown jovyan:users /home/jovyan/work


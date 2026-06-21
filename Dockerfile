FROM ubuntu:26.04

RUN apt-get update && apt-get install -y \
    git curl wget zip unzip \
    python3 python3-pip python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

# install latest cloc
ARG CLOC_VER=2.08
RUN cd /tmp \
    && wget https://github.com/AlDanial/cloc/releases/download/v${CLOC_VER}/cloc-${CLOC_VER}.tar.gz \
    && tar -zxf cloc-${CLOC_VER}.tar.gz \
    && cp cloc-${CLOC_VER}/cloc /usr/local/bin \
    && rm -rf cloc-*

# ARG UID=1001
# ARG USER=developer
# RUN useradd -m -u ${UID} ${USER}

USER ubuntu
WORKDIR /home/ubuntu
COPY --chown=ubuntu requirements.txt ./requirements.txt
RUN python3 -m pip install --upgrade pip --break-system-packages \
    && python3 -m pip install --no-cache-dir -r requirements.txt --break-system-packages

CMD ["/bin/bash"]

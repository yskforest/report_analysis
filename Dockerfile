FROM ubuntu:26.04

RUN apt-get update && apt-get install -y \
    git curl wget zip unzip \
    python3 python3-pip python-is-python3 \
    lsb-release software-properties-common \
    openjdk-21-jre-headless xalan \
    && rm -rf /var/lib/apt/lists/*

# install latest cloc
ARG CLOC_VER=2.08
RUN cd /tmp \
    && wget https://github.com/AlDanial/cloc/releases/download/v${CLOC_VER}/cloc-${CLOC_VER}.tar.gz \
    && tar -zxf cloc-${CLOC_VER}.tar.gz \
    && cp cloc-${CLOC_VER}/cloc /usr/local/bin \
    && rm -rf cloc-*

# install PMD
ARG PMD_VER=7.26.0
RUN cd /opt && \
    curl -L -o pmd.zip https://github.com/pmd/pmd/releases/download/pmd_releases%2F${PMD_VER}/pmd-dist-${PMD_VER}-bin.zip \
    && unzip pmd.zip && rm pmd.zip \
    && mv pmd-bin-${PMD_VER} pmd \
    && rm -rf /opt/pmd/docs /opt/pmd/etc/testresources
ENV PATH="/opt/pmd/bin:$PATH"

# install stable latest clang & clang-format
RUN cd /tmp \
    && wget https://apt.llvm.org/llvm.sh \
    && chmod +x llvm.sh \
    && ./llvm.sh \
    && CLANG_VER=$(ls /usr/bin/clang-[0-9]* | grep -o -E '[0-9]+$' | head -n 1) \
    && apt-get install -y clang-format-${CLANG_VER} \
    && update-alternatives --install /usr/bin/clang clang /usr/bin/clang-${CLANG_VER} 100 \
    && update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-${CLANG_VER} 100 \
    && update-alternatives --install /usr/bin/clang-format clang-format /usr/bin/clang-format-${CLANG_VER} 100 \
    && rm llvm.sh 

# ARG UID=1001
# ARG USER=developer
# RUN useradd -m -u ${UID} ${USER}

USER ubuntu
WORKDIR /home/ubuntu
COPY --chown=ubuntu requirements.txt ./requirements.txt
RUN python3 -m pip install --upgrade pip --break-system-packages \
    && python3 -m pip install --no-cache-dir -r requirements.txt --break-system-packages

CMD ["/bin/bash"]

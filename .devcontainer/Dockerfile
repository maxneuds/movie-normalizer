FROM python:3.14-bookworm

ENV USERNAME=dev
ARG UID
ARG GID
ARG DOCKER_GID

# Setup container user, groups and workspace
RUN groupadd -g ${GID} ${USERNAME} && \
    useradd -m -u ${UID} -g ${GID} ${USERNAME} && \
    mkdir /workspace && chown ${USERNAME}:${USERNAME} /workspace

# Update repo
RUN apt-get update

# Update ca-certificates
RUN apt-get install -y ca-certificates && update-ca-certificates

# Make sure locals are set to en_US.UTF-8
RUN apt-get install -y locales && \
    echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# <- Python ->
RUN apt-get install -y \
    build-essential libffi-dev libssl-dev zlib1g-dev libbz2-dev \
    libreadline-dev libsqlite3-dev python3-dev
# <- Python ->

# <- Audio & Video ->
RUN apt-get install -y \
    ffmpeg opus-tools libopus-dev mkvtoolnix
# <- Audio & Video ->

# <- DEVCONTAINER ->
# Enable sudo permissons for container user
RUN apt-get install -y sudo && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers
# Install zsh and other useful packages
RUN apt-get install -y \
    git wget curl unzip rsync zsh htop vim neofetch
# Install Docker
RUN groupadd -g ${DOCKER_GID} docker
RUN apt-get install -y \
    apt-transport-https ca-certificates curl gnupg lsb-release
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
RUN apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io
# Add container user to docker group
RUN usermod -aG docker ${USERNAME}
# Setup the environment for the container user
RUN chsh -s /bin/zsh ${USERNAME}
# Switch to container user and set home directory
USER ${USERNAME}
# Install oh-my-zsh
RUN sh -c "$(wget https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh -O -)" "" --unattended
# enable command completion and git support in zsh
RUN git clone https://github.com/zsh-users/zsh-completions ~/.oh-my-zsh/custom/plugins/zsh-completions
RUN git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ~/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting
RUN git clone https://github.com/zsh-users/zsh-autosuggestions ~/.oh-my-zsh/custom/plugins/zsh-autosuggestions
RUN sed -i 's/plugins=(git)/plugins=(git zsh-completions zsh-syntax-highlighting zsh-autosuggestions)/' ~/.zshrc
RUN sed -i 's/ZSH_THEME="robbyrussell"/ZSH_THEME="agnoster"/' ~/.zshrc
RUN echo 'prompt_context() {}' >> ~/.zshrc
# Command alias
RUN echo 'alias ll="ls -lah --color=auto"' >> ~/.zshrc
RUN echo 'alias cp="rsync -avh --progress"' >> ~/.zshrc
# Install aws tools
RUN pip install awscli
# Switch back to root user
USER root
# <- DEVCONTAINER ->

# Switch user
USER ${USERNAME}

# Install poetry
RUN pip install poetry
ENV PATH="/home/${USERNAME}/.local/bin:${PATH}"
ENV POETRY_VIRTUALENVS_CREATE=true
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV POETRY_NO_INTERACTION=1

# Entrypoint
CMD ["/bin/zsh"]

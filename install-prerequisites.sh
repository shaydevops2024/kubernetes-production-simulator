#!/bin/bash
# install-prerequisites.sh
# Interactive script to check and install prerequisites for Kubernetes Production Simulator

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# ============================================
# HELPER FUNCTIONS
# ============================================
print_header() {
    echo ""
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}============================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Progress bar function
show_progress() {
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local completed=$((width * current / total))
    local remaining=$((width - completed))

    printf "\r${CYAN}["
    printf "%${completed}s" | tr ' ' '▓'
    printf "%${remaining}s" | tr ' ' '░'
    printf "] ${percentage}%% ${NC}"
}

# ============================================
# START
# ============================================
clear
print_header "KUBERNETES PRODUCTION SIMULATOR - PREREQUISITES CHECK"

echo -e "${YELLOW}This script will check and help install required tools${NC}"
echo ""
echo -e "${CYAN}Checking for:${NC}"
echo "  • Docker"
echo "  • Docker Compose"
echo "  • kubectl"
echo "  • kind"
echo "  • Helm"
echo "  • ArgoCD CLI"
echo "  • Terraform"
echo "  • Ansible"
echo "  • Jenkins"
echo ""

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    OS_VERSION=$VERSION_ID
else
    OS=$(uname -s)
fi

# Detect if WSL
if grep -qi microsoft /proc/version 2>/dev/null; then
    IS_WSL=true
    print_info "Detected: Windows Subsystem for Linux (WSL)"
elif [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    IS_WSL=false
    print_info "Detected: $PRETTY_NAME"
else
    IS_WSL=false
    print_info "Detected: $OS"
fi

echo ""
echo -e "${YELLOW}Starting verification...${NC}"
echo ""
sleep 1

# ============================================
# CHECK INSTALLATIONS
# ============================================

# Array to store check results
declare -A INSTALLED
declare -A VERSIONS
declare -a MISSING_TOOLS
declare -a MISSING_NAMES

TOOLS=(
    "docker"
    "docker-compose"
    "kubectl"
    "kind"
    "helm"
    "argocd"
    "terraform"
    "ansible"
    "jenkins"
)

TOOL_NAMES=(
    "Docker"
    "Docker Compose"
    "kubectl"
    "kind"
    "Helm"
    "ArgoCD CLI"
    "Terraform"
    "Ansible"
    "Jenkins"
)

TOTAL_CHECKS=${#TOOLS[@]}
CURRENT_CHECK=0

# Check each tool
for i in "${!TOOLS[@]}"; do
    CURRENT_CHECK=$((CURRENT_CHECK + 1))
    tool="${TOOLS[$i]}"

    show_progress $CURRENT_CHECK $TOTAL_CHECKS
    sleep 0.3  # Small delay for visual effect

    case $tool in
        "docker")
            if command -v docker &>/dev/null; then
                INSTALLED[$tool]=true
                VERSIONS[$tool]=$(docker --version 2>/dev/null | cut -d' ' -f3 | cut -d',' -f1)
            else
                INSTALLED[$tool]=false
                MISSING_TOOLS+=("$tool")
                MISSING_NAMES+=("${TOOL_NAMES[$i]}")
            fi
            ;;
        "docker-compose")
            if command -v docker-compose &>/dev/null || docker compose version &>/dev/null; then
                INSTALLED[$tool]=true
                if command -v docker-compose &>/dev/null; then
                    VERSIONS[$tool]=$(docker-compose --version 2>/dev/null | cut -d' ' -f4 | cut -d',' -f1)
                else
                    VERSIONS[$tool]=$(docker compose version --short 2>/dev/null)
                fi
            else
                INSTALLED[$tool]=false
                MISSING_TOOLS+=("$tool")
                MISSING_NAMES+=("${TOOL_NAMES[$i]}")
            fi
            ;;
        "kubectl")
            if command -v kubectl &>/dev/null; then
                INSTALLED[$tool]=true
                VERSIONS[$tool]=$(kubectl version --client --short 2>/dev/null | cut -d' ' -f3 || kubectl version --client -o json 2>/dev/null | grep -oP '"gitVersion": "\K[^"]+' || echo "installed")
            else
                INSTALLED[$tool]=false
                MISSING_TOOLS+=("$tool")
                MISSING_NAMES+=("${TOOL_NAMES[$i]}")
            fi
            ;;
        "kind")
            if command -v kind &>/dev/null; then
                INSTALLED[$tool]=true
                VERSIONS[$tool]=$(kind version 2>/dev/null | cut -d' ' -f2)
            else
                INSTALLED[$tool]=false
                MISSING_TOOLS+=("$tool")
                MISSING_NAMES+=("${TOOL_NAMES[$i]}")
            fi
            ;;
        "helm")
            if command -v helm &>/dev/null; then
                INSTALLED[$tool]=true
                VERSIONS[$tool]=$(helm version --short 2>/dev/null | cut -d'+' -f1 | cut -d'v' -f2)
            else
                INSTALLED[$tool]=false
                MISSING_TOOLS+=("$tool")
                MISSING_NAMES+=("${TOOL_NAMES[$i]}")
            fi
            ;;
        "argocd")
            if command -v argocd &>/dev/null; then
                INSTALLED[$tool]=true
                VERSIONS[$tool]=$(argocd version --client --short 2>/dev/null | cut -d':' -f2 | cut -d'+' -f1 | xargs || echo "installed")
            else
                INSTALLED[$tool]=false
                MISSING_TOOLS+=("$tool")
                MISSING_NAMES+=("${TOOL_NAMES[$i]}")
            fi
            ;;
        "terraform")
            if command -v terraform &>/dev/null; then
                INSTALLED[$tool]=true
                VERSIONS[$tool]=$(terraform version -json 2>/dev/null | grep -oP '"terraform_version": "\K[^"]+' || terraform version | head -1 | cut -d'v' -f2)
            else
                INSTALLED[$tool]=false
                MISSING_TOOLS+=("$tool")
                MISSING_NAMES+=("${TOOL_NAMES[$i]}")
            fi
            ;;
        "ansible")
            if command -v ansible &>/dev/null; then
                INSTALLED[$tool]=true
                VERSIONS[$tool]=$(ansible --version 2>/dev/null | head -1 | cut -d' ' -f3 | cut -d']' -f1 | tr -d '[')
            else
                INSTALLED[$tool]=false
                MISSING_TOOLS+=("$tool")
                MISSING_NAMES+=("${TOOL_NAMES[$i]}")
            fi
            ;;
        "jenkins")
            # Check if Jenkins is installed (systemd service or java -jar)
            if systemctl is-active --quiet jenkins 2>/dev/null || command -v jenkins &>/dev/null; then
                INSTALLED[$tool]=true
                VERSIONS[$tool]="installed"
            else
                INSTALLED[$tool]=false
                MISSING_TOOLS+=("$tool")
                MISSING_NAMES+=("${TOOL_NAMES[$i]}")
            fi
            ;;
    esac
done

# Complete progress bar
show_progress $TOTAL_CHECKS $TOTAL_CHECKS
echo ""
echo ""

# ============================================
# DISPLAY RESULTS
# ============================================
print_header "VERIFICATION RESULTS"

echo -e "${GREEN}✅ INSTALLED:${NC}"
INSTALLED_COUNT=0
for i in "${!TOOLS[@]}"; do
    tool="${TOOLS[$i]}"
    if [ "${INSTALLED[$tool]}" = true ]; then
        INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
        version="${VERSIONS[$tool]}"
        printf "  ${GREEN}✓${NC} %-20s ${CYAN}(v%s)${NC}\n" "${TOOL_NAMES[$i]}" "$version"
    fi
done

if [ $INSTALLED_COUNT -eq 0 ]; then
    echo "  ${YELLOW}None${NC}"
fi

echo ""

# Check if anything is missing
if [ ${#MISSING_TOOLS[@]} -eq 0 ]; then
    echo ""
    print_success "All prerequisites are installed!"
    echo ""
    echo -e "${CYAN}You're ready to use the Kubernetes Production Simulator!${NC}"
    echo ""
    echo "Run one of these scripts to get started:"
    echo -e "  ${GREEN}./kind_setup.sh${NC}       - Deploy to Kind (local)"
    echo -e "  ${GREEN}./k8s_setup.sh${NC}        - Deploy to cloud Kubernetes"
    echo ""
    exit 0
fi

# Display missing tools
echo -e "${RED}❌ MISSING:${NC}"
for i in "${!MISSING_TOOLS[@]}"; do
    idx=$((i + 1))
    printf "  ${RED}%2d.${NC} %s\n" "$idx" "${MISSING_NAMES[$i]}"
done

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════${NC}"
echo ""

# ============================================
# ASK USER WHAT TO INSTALL
# ============================================
echo -e "${CYAN}Which tools would you like to install?${NC}"
echo ""
echo "Enter the numbers separated by commas (e.g., 1,3,5)"
echo "Or press Ctrl+C to exit"
echo ""
read -p "Your choice: " USER_CHOICE

# Parse user input
IFS=',' read -ra SELECTED <<< "$USER_CHOICE"

# Validate and collect tools to install
declare -a TOOLS_TO_INSTALL
declare -a NAMES_TO_INSTALL

for selection in "${SELECTED[@]}"; do
    # Trim whitespace
    selection=$(echo "$selection" | xargs)

    # Validate number
    if ! [[ "$selection" =~ ^[0-9]+$ ]]; then
        print_error "Invalid selection: $selection"
        continue
    fi

    # Check if in range
    if [ "$selection" -lt 1 ] || [ "$selection" -gt "${#MISSING_TOOLS[@]}" ]; then
        print_error "Number out of range: $selection"
        continue
    fi

    # Add to install list (arrays are 0-indexed)
    idx=$((selection - 1))
    TOOLS_TO_INSTALL+=("${MISSING_TOOLS[$idx]}")
    NAMES_TO_INSTALL+=("${MISSING_NAMES[$idx]}")
done

# Check if any valid selections
if [ ${#TOOLS_TO_INSTALL[@]} -eq 0 ]; then
    print_warning "No valid selections made. Exiting."
    exit 0
fi

# ============================================
# CONFIRM INSTALLATION
# ============================================
echo ""
print_header "INSTALLATION PLAN"

echo -e "${CYAN}The following tools will be installed:${NC}"
for name in "${NAMES_TO_INSTALL[@]}"; do
    echo "  • $name"
done

echo ""
read -p "Proceed with installation? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    print_warning "Installation cancelled"
    exit 0
fi

# ============================================
# INSTALL TOOLS
# ============================================
print_header "INSTALLING SELECTED TOOLS"

# Update package list first if needed
NEEDS_APT_UPDATE=false
for tool in "${TOOLS_TO_INSTALL[@]}"; do
    if [[ "$tool" =~ ^(ansible)$ ]]; then
        NEEDS_APT_UPDATE=true
        break
    fi
done

if [ "$NEEDS_APT_UPDATE" = true ]; then
    echo ""
    echo -e "${CYAN}Updating package lists...${NC}"
    sudo apt-get update -qq
    print_success "Package lists updated"
fi

# Install each tool
for i in "${!TOOLS_TO_INSTALL[@]}"; do
    tool="${TOOLS_TO_INSTALL[$i]}"
    name="${NAMES_TO_INSTALL[$i]}"

    echo ""
    echo -e "${BLUE}▶ Installing ${name}...${NC}"
    echo ""

    case $tool in
        "docker")
            echo "Installing Docker..."
            # Remove old versions
            sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

            # Install dependencies
            sudo apt-get install -y ca-certificates curl gnupg lsb-release

            # Add Docker GPG key
            sudo mkdir -p /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

            # Add Docker repository
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

            # Install Docker
            sudo apt-get update -qq
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

            # Add user to docker group
            sudo usermod -aG docker $USER

            print_success "Docker installed! (You may need to log out and back in for group changes)"
            ;;

        "docker-compose")
            echo "Installing Docker Compose..."
            # Install standalone docker-compose
            COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep -oP '"tag_name": "\K(.*)(?=")')
            sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            sudo chmod +x /usr/local/bin/docker-compose

            print_success "Docker Compose installed!"
            ;;

        "kubectl")
            echo "Installing kubectl..."
            # Download latest kubectl
            curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

            # Install kubectl
            sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
            rm kubectl

            print_success "kubectl installed!"
            ;;

        "kind")
            echo "Installing kind..."
            # Download and install kind
            curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
            chmod +x ./kind
            sudo mv ./kind /usr/local/bin/kind

            print_success "kind installed!"
            ;;

        "helm")
            echo "Installing Helm..."
            curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

            print_success "Helm installed!"
            ;;

        "argocd")
            echo "Installing ArgoCD CLI..."
            # Download latest ArgoCD CLI
            ARGOCD_VERSION=$(curl -s https://api.github.com/repos/argoproj/argo-cd/releases/latest | grep -oP '"tag_name": "\K(.*)(?=")')
            curl -sSL -o argocd-linux-amd64 https://github.com/argoproj/argo-cd/releases/download/${ARGOCD_VERSION}/argocd-linux-amd64
            sudo install -m 555 argocd-linux-amd64 /usr/local/bin/argocd
            rm argocd-linux-amd64

            print_success "ArgoCD CLI installed!"
            ;;

        "terraform")
            echo "Installing Terraform..."
            # Add HashiCorp GPG key
            wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg

            # Add HashiCorp repository
            echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list

            # Install Terraform
            sudo apt-get update -qq
            sudo apt-get install -y terraform

            print_success "Terraform installed!"
            ;;

        "ansible")
            echo "Installing Ansible..."
            sudo apt-get install -y software-properties-common
            sudo add-apt-repository --yes --update ppa:ansible/ansible
            sudo apt-get install -y ansible

            print_success "Ansible installed!"
            ;;

        "jenkins")
            echo "Installing Jenkins..."
            # Add Jenkins repository
            curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key | sudo tee /usr/share/keyrings/jenkins-keyring.asc > /dev/null
            echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/" | sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null

            # Install Java (required for Jenkins)
            sudo apt-get update -qq
            sudo apt-get install -y fontconfig openjdk-17-jre

            # Install Jenkins
            sudo apt-get install -y jenkins

            # Start Jenkins
            sudo systemctl enable jenkins
            sudo systemctl start jenkins

            print_success "Jenkins installed and started!"
            print_info "Access Jenkins at: http://localhost:8080"
            print_info "Get initial admin password: sudo cat /var/lib/jenkins/secrets/initialAdminPassword"
            ;;
    esac
done

# ============================================
# FINAL SUMMARY
# ============================================
print_header "INSTALLATION COMPLETE"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              INSTALLATION SUCCESSFUL!                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${CYAN}✅ INSTALLED TOOLS:${NC}"
for name in "${NAMES_TO_INSTALL[@]}"; do
    echo "  ✓ $name"
done
echo ""

# Special notes
if [[ " ${TOOLS_TO_INSTALL[@]} " =~ " docker " ]]; then
    print_warning "IMPORTANT: You need to log out and log back in for Docker group changes to take effect!"
    echo "  Or run: newgrp docker"
    echo ""
fi

if [[ " ${TOOLS_TO_INSTALL[@]} " =~ " jenkins " ]]; then
    print_info "Jenkins is running on port 8080"
    echo "  Access: http://localhost:8080"
    echo "  Get password: sudo cat /var/lib/jenkins/secrets/initialAdminPassword"
    echo ""
fi

echo -e "${CYAN}🎯 NEXT STEPS:${NC}"
echo ""
echo "  To verify installations, run this script again:"
echo -e "  ${GREEN}./install-prerequisites.sh${NC}"
echo ""
echo "  To deploy the Kubernetes Production Simulator:"
echo -e "  ${GREEN}./kind_setup.sh${NC}       - Local deployment with Kind"
echo -e "  ${GREEN}./k8s_setup.sh${NC}        - Cloud Kubernetes deployment"
echo ""

print_success "You're all set! 🚀"
echo ""

# Minimal Python bootstrap for install.sh. No downloaded scripts are executed.
ember_bootstrap_python() {
    local ember_check=0 ember_yes=0 ember_package='' ember_family='' ember_value ember_key
    local ember_id='' ember_like='' ember_arg ember_candidate
    local ember_index ember_has_indexes=0 ember_status=0
    for ember_arg in "$@"; do
        case "$ember_arg" in
            --check|--no-deps|--skip-check|--help|-h) ember_check=1 ;;
            --yes) ember_yes=1 ;;
        esac
    done
    if [ "$(uname -s)" != Linux ]; then
        printf '%s\n' 'Emberbox Audio needs a Linux desktop.' >&2; return 1
    fi
    if [ "$(id -u)" = 0 ] && [ "$ember_check" = 0 ]; then
        printf '%s\n' 'Run ./install.sh as your normal user. Only system packages use sudo.' >&2; return 1
    fi
    if [ -n "${EMBERBOX_PYTHON:-}" ]; then
        ember_candidate=$(command -v "$EMBERBOX_PYTHON" || true)
    elif [ -x /usr/bin/python3 ]; then
        ember_candidate=/usr/bin/python3
    else
        ember_candidate=$(command -v python3 || true)
    fi
    if [ -n "$ember_candidate" ] && [ -x "$ember_candidate" ]; then
        if ! "$ember_candidate" -B -c 'import sys;sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
            printf '%s\n' 'Emberbox needs Python 3.10+. Use a current system Python and retry.' >&2; return 1
        fi
        EMBERBOX_BOOTSTRAP_PYTHON=$ember_candidate; return 0
    fi
    printf '\n%s\n' '  EMBERBOX AUDIO · Python bootstrap'
    if [ "$ember_check" = 1 ] || [ -n "${EMBERBOX_PYTHON:-}" ]; then
        printf '%s\n' 'Python 3.10+ is missing. Install Python or correct EMBERBOX_PYTHON, then retry.' >&2; return 1
    fi
    if [ -r /etc/os-release ]; then
        while IFS='=' read -r ember_key ember_value; do
            ember_value=${ember_value#\"}; ember_value=${ember_value%\"}
            ember_value=${ember_value#\'}; ember_value=${ember_value%\'}
            case "$ember_key" in ID) ember_id=$ember_value ;; ID_LIKE) ember_like=$ember_value ;; esac
        done < /etc/os-release
    fi
    case "$ember_id" in
        steamos|nixos|bazzite|silverblue|kinoite|bluefin|aurora|aeon|kalpa|opensuse-microos)
            printf '%s\n' 'This system needs its own software tools. Install Python there, then retry.' >&2; return 1 ;;
    esac
    if [ -e /run/ostree-booted ] || [ -e /usr/share/ublue-os/image-info.json ]; then
        printf '%s\n' 'Immutable system detected. Install Python with its supported software tools.' >&2; return 1
    fi
    case " $ember_id $ember_like " in
        *' arch '*) ember_family=arch; ember_package=python ;;
        *' debian '*|*' ubuntu '*) ember_family=debian; ember_package=python3 ;;
        *' fedora '*) ember_family=fedora; ember_package=python3 ;;
        *' opensuse '*|*' opensuse-tumbleweed '*|*' opensuse-leap '*|*' suse '*) ember_family=opensuse; ember_package=python3 ;;
        *) printf '%s\n' 'Unknown distribution. Install Python 3.10+ with your package manager, then retry.' >&2; return 1 ;;
    esac
    if ! command -v sudo >/dev/null 2>&1; then
        printf '%s\n' 'sudo is unavailable. Ask your administrator to install Python 3.10+.' >&2; return 1
    fi
    local -a ember_command
    case "$ember_family" in
        arch) ember_command=(sudo pacman -S --needed); [ "$ember_yes" = 0 ] || ember_command+=(--noconfirm) ;;
        debian) ember_command=(sudo apt-get install --no-install-recommends); [ "$ember_yes" = 0 ] || ember_command+=(-y) ;;
        fedora) ember_command=(sudo dnf install); [ "$ember_yes" = 0 ] || ember_command+=(-y) ;;
        opensuse) ember_command=(sudo zypper); [ "$ember_yes" = 0 ] || ember_command+=(--non-interactive); ember_command+=(install --no-recommends) ;;
    esac
    ember_command+=("$ember_package")
    if [ "$ember_yes" = 0 ] && [ ! -t 0 ]; then
        printf '%s\n' 'Run this in a terminal, or explicitly pass --yes.' >&2; return 1
    fi
    if [ "$ember_family" = debian ]; then
        if [ -d /var/lib/apt/lists ] && { [ ! -r /var/lib/apt/lists ] || [ ! -x /var/lib/apt/lists ]; }; then
            printf '%s\n' 'Cannot inspect apt package indexes. Ask your administrator to refresh them.' >&2; return 1
        fi
        for ember_index in /var/lib/apt/lists/*Packages*; do
            if [ -f "$ember_index" ] && [ -s "$ember_index" ]; then ember_has_indexes=1; break; fi
        done
        if [ "$ember_has_indexes" = 0 ]; then
            printf '  $ '; printf '%q ' sudo apt-get update; printf '\n'
            sudo apt-get update || {
                ember_status=$?
                printf '%s\n' 'Package indexes could not be refreshed. Run sudo apt-get update, then retry the installer.' >&2
                return "$ember_status"
            }
        fi
    fi
    printf '  $ '; printf '%q ' "${ember_command[@]}"; printf '\n'
    "${ember_command[@]}" || {
        ember_status=$?
        if [ "$ember_family" = debian ] && [ "$ember_status" = 100 ]; then
            printf '%s\n' 'Refresh package indexes with sudo apt-get update, then retry the installer.' >&2
        fi
        return "$ember_status"
    }
    EMBERBOX_BOOTSTRAP_PYTHON=$(command -v python3 || true)
    if [ -z "$EMBERBOX_BOOTSTRAP_PYTHON" ]; then
        printf '%s\n' 'Python is still unavailable. Installation stopped.' >&2; return 1
    fi
}

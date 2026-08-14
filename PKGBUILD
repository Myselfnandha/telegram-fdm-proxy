# Maintainer: Nandha <myselfnandha@github>
pkgname=tg-fdm-proxy
pkgver=1.2.0
pkgrel=1
pkgdesc="High-speed HTTP streaming proxy for Telegram media downloads with Free Download Manager, aria2, and system tray integration"
arch=('any')
url="https://github.com/Myselfnandha/AeroHub"
license=('MIT')
depends=(
    'python'
    'python-telethon'
    'python-aiohttp'
    'python-dotenv'
    'python-pillow'
    'python-pystray'
    'python-psutil'
    'python-cryptg'
)
optdepends=(
    'freedownloadmanager: Free Download Manager integration (native or flatpak)'
    'aria2: High-speed multi-connection CLI downloader'
    'libnotify: Native desktop notification alerts'
)
backup=('etc/tg-fdm-proxy/env.example')
source=()
sha256sums=()

package() {
    # Application code install
    install -Dm755 "${srcdir}/../tg_fdm_proxy.py" "${pkgdir}/usr/share/${pkgname}/tg_fdm_proxy.py"
    install -Dm755 "${srcdir}/../settings_gui.py" "${pkgdir}/usr/share/${pkgname}/settings_gui.py"

    # Wrapper script in /usr/bin
    mkdir -p "${pkgdir}/usr/bin"
    cat << 'EOF' > "${pkgdir}/usr/bin/${pkgname}"
#!/bin/sh
exec python3 /usr/share/tg-fdm-proxy/tg_fdm_proxy.py "$@"
EOF
    chmod 755 "${pkgdir}/usr/bin/${pkgname}"

    # Desktop entry
    install -Dm644 "${srcdir}/../assets/tg-fdm-proxy.desktop" "${pkgdir}/usr/share/applications/${pkgname}.desktop"

    # Application icons
    install -Dm644 "${srcdir}/../assets/tg-fdm-proxy.png" "${pkgdir}/usr/share/icons/hicolor/256x256/apps/${pkgname}.png"
    install -Dm644 "${srcdir}/../assets/tg-fdm-proxy.svg" "${pkgdir}/usr/share/icons/hicolor/scalable/apps/${pkgname}.svg"

    # Systemd User Unit
    install -Dm644 "${srcdir}/../assets/tg-fdm-proxy.service" "${pkgdir}/usr/lib/systemd/user/${pkgname}.service"
}

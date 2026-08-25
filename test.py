import ssl
import socket
import socks

# ========== 代理配置 ==========
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 7890
SOCKS_TYPE = socks.SOCKS5

host = "smtp.gmail.com"
port = 465

# 覆盖系统默认socket，让所有网络请求走socks代理
socks.set_default_proxy(SOCKS_TYPE, PROXY_HOST, PROXY_PORT)
socket.socket = socks.socksocket

# 开始SSL握手测试
try:
    sock = socket.socket()
    sock.connect((host, port))
    ctx = ssl.create_default_context()
    s = ctx.wrap_socket(sock, server_hostname=host)
    print("✅ 通过代理 SSL握手成功")
    s.close()
except Exception as e:
    print(f"❌ 通过代理失败 {type(e).__name__}: {e} {e}")

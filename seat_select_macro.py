import base64
import json
import os
import socket
import struct
import time
import urllib.request


GRADE_NAME = "중립구역"
AUTO_ASSIGN_TEXT = "자동 배정받기"
COUNT_COMPLETE_TEXT = "선택 완료"
SUCCESS_TEXT = "좌석 1개가 자동 배정됐어요"
DEBUGGER_URL = "http://127.0.0.1:9222/json"
RETRY_DELAY_SECONDS = 0.3


class ChromeWebSocket:
    def __init__(self, websocket_url):
        self.host, self.port, self.path = self._parse_url(websocket_url)
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
        self.next_id = 1
        self._handshake()

    def _parse_url(self, url):
        if not url.startswith("ws://"):
            raise ValueError(f"Unsupported WebSocket URL: {url}")
        rest = url[len("ws://") :]
        host_port, path = rest.split("/", 1)
        if ":" in host_port:
            host, port = host_port.split(":", 1)
            return host, int(port), "/" + path
        return host_port, 80, "/" + path

    def _handshake(self):
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = self.sock.recv(4096)
        if b" 101 " not in response:
            raise RuntimeError("Chrome DevTools WebSocket connection failed.")

    def command(self, method, params=None):
        message_id = self.next_id
        self.next_id += 1
        payload = json.dumps(
            {"id": message_id, "method": method, "params": params or {}},
            ensure_ascii=False,
        ).encode("utf-8")
        self._send_frame(payload)

        while True:
            message = json.loads(self._recv_frame().decode("utf-8"))
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result", {})

    def _send_frame(self, payload):
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack(">H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack(">Q", length))

        mask = os.urandom(4)
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def _recv_exact(self, size):
        data = b""
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise RuntimeError("Chrome DevTools connection closed.")
            data += chunk
        return data

    def _recv_frame(self):
        first, second = self._recv_exact(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack(">H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._recv_exact(8))[0]

        if second & 0x80:
            mask = self._recv_exact(4)
            payload = self._recv_exact(length)
            payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        else:
            payload = self._recv_exact(length)

        if opcode == 0x8:
            raise RuntimeError("Chrome DevTools WebSocket closed.")
        return payload


def get_current_page_websocket_url():
    with urllib.request.urlopen(DEBUGGER_URL, timeout=10) as response:
        pages = json.loads(response.read().decode("utf-8"))

    for page in pages:
        if page.get("type") == "page" and page.get("webSocketDebuggerUrl"):
            return page["webSocketDebuggerUrl"]

    raise RuntimeError("No connectable Chrome tab found.")


def evaluate(chrome, expression):
    result = chrome.command(
        "Runtime.evaluate",
        {
            "expression": expression,
            "awaitPromise": True,
            "returnByValue": True,
        },
    )
    return result.get("result", {}).get("value")


def mouse_click(chrome, x, y):
    for event in [
        {"type": "mouseMoved", "button": "none", "buttons": 0},
        {"type": "mousePressed", "button": "left", "buttons": 1, "clickCount": 1},
        {"type": "mouseReleased", "button": "left", "buttons": 0, "clickCount": 1},
    ]:
        event.update({"x": x, "y": y, "pointerType": "mouse"})
        chrome.command("Input.dispatchMouseEvent", event)


def is_success_visible(chrome):
    return bool(
        evaluate(
            chrome,
            f"""
            (() => document.body && document.body.textContent.includes({SUCCESS_TEXT!r}))()
            """,
        )
    )


def click_point_result(chrome, result, label):
    if not result or not result.get("ok"):
        return False
    if result.get("disabled"):
        print(f"{label} disabled")
        return False

    mouse_click(chrome, result["x"], result["y"])
    print(f"{label} clicked")
    return True


def find_grade_button(chrome):
    return evaluate(
        chrome,
        f"""
        (() => {{
          const gradeName = {GRADE_NAME!r};
          const buttons = [...document.querySelectorAll('button')];

          for (const button of buttons) {{
            const buttonText = button.textContent.replace(/\\s+/g, ' ').trim();
            const name =
              button.querySelector('[class*="SportsSeatGradeList_contentGradeName"]')?.textContent.trim() ||
              (buttonText.includes(gradeName) ? gradeName : '');
            if (name !== gradeName) continue;

            const countText =
              button.querySelector('[class*="SportsSeatGradeList_contentRemainCount"]')?.textContent.trim() ||
              buttonText.replace(gradeName, '').trim();
            const remainCount = Number(countText.replace(/[^0-9]/g, ''));
            if (Number.isFinite(remainCount) && remainCount === 0) {{
              return {{
                ok: false,
                stop: true,
                message: `${{gradeName}} remain count is 0`
              }};
            }}

            button.scrollIntoView({{ block: 'center', inline: 'center' }});
            const rect = button.getBoundingClientRect();
            return {{
              ok: true,
              x: rect.left + rect.width / 2,
              y: rect.top + rect.height / 2,
              text: buttonText,
              remainCount: Number.isFinite(remainCount) ? remainCount : null,
              disabled: Boolean(button.disabled)
            }};
          }}

          return {{ ok: false, message: 'grade button not found' }};
        }})()
        """,
    )


def find_auto_assign_button(chrome):
    return evaluate(
        chrome,
        f"""
        (() => {{
          const button = [...document.querySelectorAll('button[type="button"], button')]
            .find((item) => item.textContent.replace(/\\s+/g, ' ').trim() === {AUTO_ASSIGN_TEXT!r});
          if (!button) return {{ ok: false, message: 'auto assign button not found' }};

          button.scrollIntoView({{ block: 'center', inline: 'center' }});
          const rect = button.getBoundingClientRect();
          return {{
            ok: true,
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
            disabled: Boolean(button.disabled)
          }};
        }})()
        """,
    )


def find_increment_button(chrome):
    return evaluate(
        chrome,
        f"""
        (() => {{
          const gradeName = {GRADE_NAME!r};
          const cards = [...document.querySelectorAll('[class*="SeatCountBottomSheet_gradeCard"]')];
          const card = cards.find((item) => {{
            const name = item.querySelector('[class*="SeatCountBottomSheet_gradeNameText"]')
              ?.textContent.trim();
            return name === gradeName;
          }});
          if (!card) return {{ ok: false, message: 'count sheet not found' }};

          const input = card.querySelector('input[role="spinbutton"], input[inputmode="numeric"]');
          const increment = card.querySelector(
            'button[class*="nds-e-stepper__incrementButton"], button[class*="incrementButton"]'
          );
          if (!increment) return {{ ok: false, message: 'increment button not found' }};

          increment.scrollIntoView({{ block: 'center', inline: 'center' }});
          const rect = increment.getBoundingClientRect();
          return {{
            ok: true,
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
            disabled: Boolean(increment.disabled),
            value: input ? input.value : ''
          }};
        }})()
        """,
    )


def find_count_complete_button(chrome):
    return evaluate(
        chrome,
        f"""
        (() => {{
          const button = [...document.querySelectorAll('button[type="button"], button')]
            .find((item) => {{
              const text = item.textContent.replace(/\\s+/g, ' ').trim();
              const className = String(item.className);
              return text === {COUNT_COMPLETE_TEXT!r} && className.includes('filled_primary');
            }}) ||
            [...document.querySelectorAll('button[type="button"], button')]
              .find((item) => item.textContent.replace(/\\s+/g, ' ').trim() === {COUNT_COMPLETE_TEXT!r});
          if (!button) return {{ ok: false, message: 'count complete button not found' }};

          button.scrollIntoView({{ block: 'center', inline: 'center' }});
          const rect = button.getBoundingClientRect();
          return {{
            ok: true,
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2,
            disabled: Boolean(button.disabled)
          }};
        }})()
        """,
    )


def click_zoom_fit_button(chrome):
    result = evaluate(
        chrome,
        """
        (() => {
          const button = document.querySelector('button[class*="SeatPlan_zoomFitButton"]');
          if (!button) return { ok: false, message: 'zoom fit button not found' };

          button.scrollIntoView({ block: 'center', inline: 'center' });
          const rect = button.getBoundingClientRect();
          const x = rect.left + rect.width / 2;
          const y = rect.top + rect.height / 2;

          for (const eventName of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
            button.dispatchEvent(new MouseEvent(eventName, {
              bubbles: true,
              cancelable: true,
              view: window,
              button: 0,
              buttons: eventName.endsWith('down') ? 1 : 0
            }));
          }

          return {
            ok: true,
            x,
            y,
            disabled: Boolean(button.disabled)
          };
        })()
        """,
    )
    if not result or not result.get("ok"):
        print((result or {}).get("message", "zoom fit button not found"))
        return

    mouse_click(chrome, result["x"], result["y"])
    if result.get("disabled"):
        print("zoom fit clicked/event dispatched, but button is disabled")
    else:
        print("zoom fit clicked")


def run_once(chrome):
    if click_point_result(chrome, find_increment_button(chrome), "increment"):
        time.sleep(0.15)
        click_point_result(chrome, find_count_complete_button(chrome), "count complete")
        return "tried"

    grade_button = find_grade_button(chrome)
    if grade_button and grade_button.get("stop"):
        print(grade_button.get("message", "remain count is 0"))
        return "stop"

    if click_point_result(chrome, grade_button, "grade"):
        time.sleep(0.1)

    if click_point_result(chrome, find_auto_assign_button(chrome), "auto assign"):
        time.sleep(0.15)

    if click_point_result(chrome, find_increment_button(chrome), "increment"):
        time.sleep(0.15)
        click_point_result(chrome, find_count_complete_button(chrome), "count complete")
        return "tried"

    return "idle"


def main():
    chrome = ChromeWebSocket(get_current_page_websocket_url())
    attempt = 1

    print("Repeating until success text appears. Press Ctrl+C to stop.")
    while True:
        if is_success_visible(chrome):
            print(SUCCESS_TEXT)
            return

        print(f"Attempt {attempt}")
        status = run_once(chrome)
        if status == "stop":
            return
        if status == "tried" and not is_success_visible(chrome):
            click_zoom_fit_button(chrome)
        attempt += 1
        time.sleep(RETRY_DELAY_SECONDS)


if __name__ == "__main__":
    main()

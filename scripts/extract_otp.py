"""
Decode Google Authenticator Migration URI to extract TOTP secret key.

Usage:
    python scripts/extract_otp.py "otpauth-migration://offline?data=..."
"""
import urllib.parse
import base64
import sys


def decode_migration(uri):
    try:
        parsed = urllib.parse.urlparse(uri)
        query = urllib.parse.parse_qs(parsed.query)
        data_b64 = query.get('data', [''])[0]
        if not data_b64:
            print("[FAIL] Missing 'data' parameter.")
            return
        raw_data = base64.b64decode(urllib.parse.unquote(data_b64))

        i = 0
        while i < len(raw_data):
            key = raw_data[i]
            i += 1
            if key == 0x0a:
                length = raw_data[i]
                i += 1
                otp_payload = raw_data[i:i+length]
                i += length

                j = 0
                secret_b32 = None
                name = None
                issuer = None
                while j < len(otp_payload):
                    t = otp_payload[j]
                    j += 1
                    if t == 0x0a:
                        l = otp_payload[j]
                        j += 1
                        secret_bytes = otp_payload[j:j+l]
                        j += l
                        secret_b32 = base64.b32encode(secret_bytes).decode().replace('=', '')
                    elif t == 0x12:
                        l = otp_payload[j]
                        j += 1
                        name = otp_payload[j:j+l].decode('utf-8', errors='ignore')
                        j += l
                    elif t == 0x1a:
                        l = otp_payload[j]
                        j += 1
                        issuer = otp_payload[j:j+l].decode('utf-8', errors='ignore')
                        j += l
                    else:
                        wire_type = t & 7
                        if wire_type == 0:
                            while otp_payload[j] & 0x80:
                                j += 1
                            j += 1
                        elif wire_type == 2:
                            l = otp_payload[j]
                            j += 1
                            j += l
                        else:
                            break
                print("=" * 60)
                print(f"Issuer: {issuer}")
                print(f"Account: {name}")
                print(f"Secret Key: {secret_b32}")
                print("=" * 60)
    except Exception as e:
        print(f"[FAIL] Error decoding url: {e}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python scripts/extract_otp.py "otpauth-migration://offline?data=..."')
    else:
        decode_migration(sys.argv[1])

"""
Standalone SMTP relay diagnostic — answers one question: does email.essar.com:25
require per-mailbox authentication to send, or does it accept mail from this
server with an arbitrary From: address, no login at all?

Not part of the Django app — plain smtplib, no Django import, so it runs
on its own with just `python3 scripts/test_smtp_relay.py ...`.

Usage examples
--------------
# Does the relay accept mail with NO auth at all, From an arbitrary address?
python3 scripts/test_smtp_relay.py --mode noauth --from you@essar.com --to you@essar.com

# Does the shared service account (from Mst_Business_System, Oilfield
# Services row) work when authenticated?
python3 scripts/test_smtp_relay.py --mode auth --to you@essar.com

# Does the relay let an AUTHENTICATED service account send AS a different
# From address (the actual pattern this app would need for per-user mail)?
python3 scripts/test_smtp_relay.py --mode auth-spoof --from someoneelse@essar.com --to you@essar.com

Run all three in turn to build the full picture:
  1. noauth       -> relay open, no credentials needed at all (best case)
  2. auth         -> confirms the shared account itself works
  3. auth-spoof   -> confirms auth is required, but From can still be set freely
                     (i.e. no per-mailbox password needed even though the relay
                     requires *some* login)
"""

import argparse
import smtplib
import ssl
import sys
from email.message import EmailMessage

DEFAULT_HOST = "email.essar.com"
DEFAULT_PORT = 25

# Shared service account — Mst_Business_System, Business_System_id=6
# ("Oilfield Services"). Only used for --mode auth / auth-spoof.
DEFAULT_SERVICE_USER = "eosila"
DEFAULT_SERVICE_PASSWORD = "We1c0me@"
DEFAULT_SERVICE_FROM = "eosil.autoalerts@essar.com"


def send(host, port, mail_from, mail_to, subject, body, use_tls, auth_user=None, auth_password=None):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg.set_content(body)

    print(f"Connecting to {host}:{port} ...")
    with smtplib.SMTP(host, port, timeout=15) as server:
        server.set_debuglevel(1)  # prints the raw SMTP conversation
        if use_tls:
            print("Issuing STARTTLS ...")
            server.starttls(context=ssl.create_default_context())
        if auth_user:
            print(f"Authenticating as {auth_user!r} ...")
            server.login(auth_user, auth_password)
        else:
            print("Sending with NO authentication.")
        server.send_message(msg)
    print("\nSUCCESS — message accepted by the relay.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--mode",
        choices=["noauth", "auth", "auth-spoof"],
        required=True,
        help=(
            "noauth = no login, From is whatever --from you pass "
            "(tests whether the relay is open). "
            "auth = login as the shared eosila service account and send From that same address. "
            "auth-spoof = login as eosila, but send From a DIFFERENT address (tests whether an "
            "authenticated connection can still set an arbitrary From)."
        ),
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"SMTP host (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"SMTP port (default: {DEFAULT_PORT})")
    parser.add_argument("--tls", action="store_true", help="Issue STARTTLS before sending (default: off, matching current .env — this relay is configured with no TLS/SSL)")
    parser.add_argument("--from", dest="mail_from", help="From address. Required for --mode noauth/auth-spoof; defaults to the service account's own address for --mode auth.")
    parser.add_argument("--to", dest="mail_to", required=True, help="Recipient address — send this to yourself so you can check the inbox / headers.")
    parser.add_argument("--subject", default="SerosIT SMTP relay test", help="Email subject")
    parser.add_argument("--body", default="This is a test message from scripts/test_smtp_relay.py.", help="Email body text")
    parser.add_argument("--auth-user", default=DEFAULT_SERVICE_USER, help=f"Service account username (default: {DEFAULT_SERVICE_USER})")
    parser.add_argument("--auth-password", default=DEFAULT_SERVICE_PASSWORD, help="Service account password (default: the Oilfield Services row's own password)")

    args = parser.parse_args()

    if args.mode == "noauth":
        if not args.mail_from:
            parser.error("--mode noauth requires --from (the address you want to test sending AS, unauthenticated)")
        auth_user = None
        auth_password = None
        mail_from = args.mail_from
    elif args.mode == "auth":
        auth_user = args.auth_user
        auth_password = args.auth_password
        mail_from = args.mail_from or DEFAULT_SERVICE_FROM
    else:  # auth-spoof
        if not args.mail_from:
            parser.error("--mode auth-spoof requires --from (a DIFFERENT address than the service account, to test spoofing while authenticated)")
        auth_user = args.auth_user
        auth_password = args.auth_password
        mail_from = args.mail_from

    print("=" * 70)
    print(f"mode        : {args.mode}")
    print(f"host:port   : {args.host}:{args.port}")
    print(f"tls         : {args.tls}")
    print(f"from        : {mail_from}")
    print(f"to          : {args.mail_to}")
    print(f"auth as     : {auth_user or '(none)'}")
    print("=" * 70)

    try:
        send(
            args.host,
            args.port,
            mail_from,
            args.mail_to,
            args.subject,
            args.body,
            args.tls,
            auth_user,
            auth_password,
        )
    except smtplib.SMTPAuthenticationError as e:
        print(f"\nFAILED — authentication rejected: {e}")
        sys.exit(1)
    except smtplib.SMTPRecipientsRefused as e:
        print(f"\nFAILED — relay refused the recipient (this often means it needs auth, or From is not permitted): {e}")
        sys.exit(1)
    except smtplib.SMTPSenderRefused as e:
        print(f"\nFAILED — relay refused the From address (mode={args.mode} — this tells you whether spoofing From is allowed): {e}")
        sys.exit(1)
    except smtplib.SMTPException as e:
        print(f"\nFAILED — SMTP error: {e}")
        sys.exit(1)
    except OSError as e:
        print(f"\nFAILED — could not connect (network/firewall/port issue): {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

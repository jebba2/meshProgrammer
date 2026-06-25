import pytest

from meshprogrammer import crypto


def test_encrypt_then_decrypt_round_trips_with_correct_password() -> None:
    payload = {"node_id": "!a1b2c3d4", "local_config": {"device": {"role": "CLIENT"}}}

    envelope = crypto.encrypt_payload(payload, "correct horse battery staple")

    assert crypto.is_encrypted(envelope)
    assert crypto.decrypt_payload(envelope, "correct horse battery staple") == payload


def test_decrypt_with_wrong_password_raises_wrong_password_error() -> None:
    envelope = crypto.encrypt_payload({"v": 1}, "right-password")

    with pytest.raises(crypto.WrongPasswordError):
        crypto.decrypt_payload(envelope, "wrong-password")


def test_is_encrypted_is_false_for_plain_payload() -> None:
    assert crypto.is_encrypted({"node_id": "!a1b2c3d4"}) is False


def test_is_encrypted_is_true_for_envelope() -> None:
    envelope = crypto.encrypt_payload({"v": 1}, "password")

    assert crypto.is_encrypted(envelope) is True


def test_encrypt_payload_uses_a_distinct_salt_each_time() -> None:
    envelope_a = crypto.encrypt_payload({"v": 1}, "password")
    envelope_b = crypto.encrypt_payload({"v": 1}, "password")

    assert envelope_a["salt"] != envelope_b["salt"]
    assert envelope_a["ciphertext"] != envelope_b["ciphertext"]

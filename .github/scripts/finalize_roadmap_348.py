from __future__ import annotations

import json
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 6 — shared gateway transport: heartbeat failures must invalidate the pooled
# session AND notify every logical child immediately.
# ---------------------------------------------------------------------------
path = Path("custom_components/localtuya/gateway_transport.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        finally:\n            if self.alive:\n                transport = self.parent.transport\n                self.parent.transport = None\n                if transport is not None:\n                    transport.close()\n            self._disconnected = True\n''',
    '''        finally:\n            if self.alive:\n                transport = self.parent.transport\n                self.parent.transport = None\n                if transport is not None:\n                    transport.close()\n            if not self._closed:\n                # Heartbeat failure is a physical disconnect too. Notify every\n                # logical child once and make the pooled session non-reusable.\n                self.parent_disconnected()\n''',
    "gateway heartbeat disconnect",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# 6 — QR/import child metadata: parse Tuya's sub flag safely. In particular,
# the string "false" must never be truthy and accidentally turn UUID into CID.
# ---------------------------------------------------------------------------
path = Path("custom_components/localtuya/qr_onboarding.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''def _token_info(value: dict[str, Any]) -> dict[str, Any]:\n    """Keep only the token fields required by tuya-device-sharing-sdk."""\n    return {\n        key: value[key]\n        for key in _QR_TOKEN_FIELDS\n        if key in value\n    }\n\n\nclass _TokenCapture(SharingTokenListener):\n''',
    '''def _token_info(value: dict[str, Any]) -> dict[str, Any]:\n    """Keep only the token fields required by tuya-device-sharing-sdk."""\n    return {\n        key: value[key]\n        for key in _QR_TOKEN_FIELDS\n        if key in value\n    }\n\n\ndef _is_subdevice_flag(value: Any) -> bool:\n    """Normalize Tuya SDK/export sub-device flags without string truthiness."""\n    if isinstance(value, bool):\n        return value\n    if isinstance(value, (int, float)) and not isinstance(value, bool):\n        return value == 1\n    if isinstance(value, str):\n        return value.strip().lower() in {"1", "true", "yes"}\n    return False\n\n\nclass _TokenCapture(SharingTokenListener):\n''',
    "subdevice flag helper",
)
text = replace_once(
    text,
    '            is_subdevice = bool(getattr(device, "sub", False))\n',
    '            is_subdevice = _is_subdevice_flag(getattr(device, "sub", False))\n',
    "SDK subdevice flag",
)
text = replace_once(
    text,
    '    if not node_id and bool(raw.get("sub", False)) and gateway_id:\n',
    '    if not node_id and _is_subdevice_flag(raw.get("sub", False)) and gateway_id:\n',
    "import subdevice flag",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# 8 — contribution UX: ordinary mappings go through the visible GitHub action
# with a complete prefill. Oversized mappings fall back to the sanitized JSON
# review rather than silently opening an empty GitHub file.
# ---------------------------------------------------------------------------
path = Path("custom_components/localtuya/mapping_export.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "MAX_GITHUB_PREFILL_URL_LENGTH = 30000",
    "MAX_GITHUB_PREFILL_URL_LENGTH = 7500",
    "GitHub conservative prefill limit",
)
text = replace_once(
    text,
    '''    new_submission_url = _build_github_submission_url(\n        suggested_filename,\n        submission_prefill_json,\n    )\n\n    return {\n''',
    '''    new_submission_url = _build_github_submission_url(\n        suggested_filename,\n        submission_prefill_json,\n    )\n    prefill_complete = "value=" in new_submission_url\n\n    return {\n''',
    "contribution prefill state",
)
text = replace_once(
    text,
    '''        "new_submission_url": new_submission_url,\n        "preview": preview,\n''',
    '''        "new_submission_url": new_submission_url,\n        "prefill_complete": prefill_complete,\n        "preview": preview,\n''',
    "contribution prefill state result",
)
path.write_text(text, encoding="utf-8")

path = Path("custom_components/localtuya/config_flow.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        if user_input is not None:\n            if user_input.get(CONTRIBUTION_CONFIRM, False):\n                return await self.async_step_submit_to_community_catalog()\n            errors["base"] = "contribution_confirmation_required"\n''',
    '''        if user_input is not None:\n            if user_input.get(CONTRIBUTION_CONFIRM, False):\n                if self.contribution_package.get("prefill_complete", False):\n                    return await self.async_step_community_contribution_actions()\n                return await self.async_step_prepare_contribution_result()\n            errors["base"] = "contribution_confirmation_required"\n''',
    "contribution safe routing",
)
path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# 3 — complete HA Repair translations. Device-health Repairs are fixable, so
# every translation key emitted by repair_issues.py needs a complete fix_flow.
# ---------------------------------------------------------------------------
TRANSLATION_DATA = {
    "en": {
        "titles": {
            "device_health_host_unreachable": "LocalTuya cannot reach {device_name}",
            "device_health_auth_or_protocol": "LocalTuya cannot authenticate {device_name}",
            "device_health_protocol_not_detected": "LocalTuya could not detect the protocol for {device_name}",
            "device_health_empty_dps": "LocalTuya received no datapoints from {device_name}",
            "device_health_invalid_configuration": "LocalTuya found an invalid configuration for {device_name}",
            "device_health_probe_error": "LocalTuya could not complete the health check for {device_name}",
        },
        "descriptions": {
            "device_health_host_unreachable": "The device is not reachable at its saved LAN address. Rediscover the gateway/device or enter its current address manually; LocalTuya validates it before saving.",
            "device_health_auth_or_protocol": "The LAN device answered, but authentication or protocol validation failed. Refresh or enter the local key, select a protocol, or retry.",
            "device_health_protocol_not_detected": "Automatic protocol detection did not find a working Tuya LAN protocol. Select a protocol explicitly or retry.",
            "device_health_empty_dps": "The device authenticated but returned no datapoints. Retry or select a protocol explicitly before changing the configuration.",
            "device_health_invalid_configuration": "The saved LocalTuya configuration cannot be validated safely. Review credentials/protocol or retry without losing the current configuration.",
            "device_health_probe_error": "The bounded LocalTuya health check failed unexpectedly. Retry the current configuration or select a protocol explicitly.",
        },
        "host": {
            "cannot_connect": "The device did not respond at that address. Check that it is powered on and reachable from Home Assistant.",
            "invalid_auth": "The device answered, but its saved local credentials were rejected. Refresh or reconfigure the credentials before retrying.",
            "empty_dps": "The device connection succeeded, but no datapoints were returned. Retry after the device is fully online.",
            "invalid_host": "Enter a valid LAN IP address or hostname.",
            "unknown": "The address could not be validated safely. The existing configuration was left unchanged.",
            "stale": "The device address changed again while validation was running. Retry discovery or enter the current address manually.",
            "device_not_found": "The configured device was not found during LAN discovery. You can enter its current address manually.",
            "discovery_unavailable": "Automatic LAN discovery is not available right now. Enter the device address manually.",
            "discovery_failed": "Automatic LAN discovery failed. Enter the device address manually or retry later.",
            "init_title": "Repair LAN connection for {device_name}",
            "init_description": "Choose automatic rediscovery or enter the device's current LAN address. LocalTuya validates Device ID, local key, protocol and datapoints before saving any new address.",
            "rediscover": "Retry automatic LAN discovery",
            "manual_host": "Enter IP address / hostname manually",
            "manual_title": "Enter the current LAN address",
            "manual_description": "Enter the current IP address or hostname for {device_name}. The address will be saved only after a successful authenticated LocalTuya validation.",
            "host_label": "IP address / Host",
        },
        "device": {
            "abort_not_found": "The configured device no longer exists.",
            "cannot_connect": "The device could not be reached over LAN. No configuration was changed.",
            "invalid_auth": "The device rejected the saved credentials. No configuration was changed.",
            "empty_dps": "The device connected but returned no datapoints. No configuration was changed.",
            "unknown": "Validation failed safely. The existing configuration was left unchanged.",
            "qr_account_not_linked": "No Smart Life/Tuya QR account is linked to this LocalTuya entry. Enter the local key manually or re-link the account from LocalTuya options.",
            "qr_reauth_required": "The saved Tuya authorization expired. Re-link the Smart Life/Tuya account, then retry.",
            "credential_refresh_failed": "LocalTuya could not retrieve a usable local key from the linked Tuya account.",
            "init_title": "Repair {device_name}",
            "init_description": "Choose a recovery action. LocalTuya validates credentials, protocol and datapoints before saving changes.",
            "refresh_credentials": "Refresh local key from linked Tuya account",
            "manual_credentials": "Enter local key manually",
            "select_protocol": "Select protocol version",
            "retry": "Retry current configuration",
            "retry_title": "Retry {device_name}",
            "retry_description": "Validate the currently saved LAN address, credentials, protocol and datapoints again without changing them first.",
            "manual_title": "Update local key for {device_name}",
            "manual_description": "Enter the current local key. For a gateway-backed child, use the gateway local key. It is saved only after successful LAN validation.",
            "local_key": "Local key",
            "refresh_title": "Refresh local key for {device_name}",
            "refresh_description": "Synchronize the linked Smart Life/Tuya account on demand and validate the refreshed key over LAN before saving it.",
            "protocol_title": "Select protocol for {device_name}",
            "protocol_description": "Choose Auto or an explicit Tuya LAN protocol. LocalTuya validates the selection before saving it.",
            "protocol_version": "Protocol version",
        },
        "fallback_description": "This contribution is too large for a reliable GitHub prefill. Copy or review the sanitized JSON below, then choose Submit to Community Catalog. Suggested file: `{filename}`. Nothing is uploaded automatically.",
    },
    "it": {
        "titles": {
            "device_health_host_unreachable": "LocalTuya non riesce a raggiungere {device_name}",
            "device_health_auth_or_protocol": "LocalTuya non riesce ad autenticare {device_name}",
            "device_health_protocol_not_detected": "LocalTuya non ha rilevato il protocollo di {device_name}",
            "device_health_empty_dps": "LocalTuya non ha ricevuto datapoint da {device_name}",
            "device_health_invalid_configuration": "LocalTuya ha rilevato una configurazione non valida per {device_name}",
            "device_health_probe_error": "LocalTuya non ha completato il controllo di {device_name}",
        },
        "descriptions": {
            "device_health_host_unreachable": "Il dispositivo non è raggiungibile all'indirizzo LAN salvato. Rileva di nuovo gateway/dispositivo oppure inserisci l'indirizzo attuale; LocalTuya lo verifica prima di salvarlo.",
            "device_health_auth_or_protocol": "Il dispositivo LAN risponde, ma autenticazione o protocollo non vengono convalidati. Aggiorna o inserisci la local key, scegli il protocollo oppure riprova.",
            "device_health_protocol_not_detected": "Il rilevamento automatico non ha trovato un protocollo Tuya LAN funzionante. Selezionalo manualmente oppure riprova.",
            "device_health_empty_dps": "Il dispositivo è autenticato ma non restituisce datapoint. Riprova o seleziona esplicitamente il protocollo prima di modificare la configurazione.",
            "device_health_invalid_configuration": "La configurazione LocalTuya salvata non può essere convalidata in sicurezza. Controlla credenziali/protocollo o riprova senza perdere la configurazione attuale.",
            "device_health_probe_error": "Il controllo limitato dello stato LocalTuya è terminato con un errore inatteso. Riprova la configurazione attuale o seleziona esplicitamente il protocollo.",
        },
        "host": {
            "cannot_connect": "Il dispositivo non risponde a questo indirizzo. Verifica che sia acceso e raggiungibile da Home Assistant.",
            "invalid_auth": "Il dispositivo risponde, ma rifiuta le credenziali locali salvate. Aggiorna o riconfigura le credenziali prima di riprovare.",
            "empty_dps": "La connessione riesce, ma il dispositivo non restituisce datapoint. Riprova quando è completamente online.",
            "invalid_host": "Inserisci un indirizzo IP LAN o un nome host valido.",
            "unknown": "Non è stato possibile convalidare l'indirizzo in sicurezza. La configurazione esistente non è stata modificata.",
            "stale": "L'indirizzo del dispositivo è cambiato di nuovo durante la verifica. Ripeti il rilevamento o inserisci manualmente l'indirizzo attuale.",
            "device_not_found": "Il dispositivo configurato non è stato trovato nella rete LAN. Puoi inserire manualmente il suo indirizzo attuale.",
            "discovery_unavailable": "Il rilevamento LAN automatico non è disponibile. Inserisci manualmente l'indirizzo del dispositivo.",
            "discovery_failed": "Il rilevamento LAN automatico non è riuscito. Inserisci manualmente l'indirizzo oppure riprova più tardi.",
            "init_title": "Ripara la connessione LAN di {device_name}",
            "init_description": "Scegli il rilevamento automatico oppure inserisci l'indirizzo LAN attuale. LocalTuya verifica ID dispositivo, local key, protocollo e datapoint prima di salvare il nuovo indirizzo.",
            "rediscover": "Ripeti il rilevamento LAN automatico",
            "manual_host": "Inserisci manualmente IP / nome host",
            "manual_title": "Inserisci l'indirizzo LAN attuale",
            "manual_description": "Inserisci l'indirizzo IP o il nome host attuale di {device_name}. Verrà salvato solo dopo una convalida LocalTuya autenticata riuscita.",
            "host_label": "Indirizzo IP / Host",
        },
        "device": {
            "abort_not_found": "Il dispositivo configurato non esiste più.",
            "cannot_connect": "Il dispositivo non è raggiungibile via LAN. Nessuna configurazione è stata modificata.",
            "invalid_auth": "Il dispositivo ha rifiutato le credenziali salvate. Nessuna configurazione è stata modificata.",
            "empty_dps": "Il dispositivo si connette ma non restituisce datapoint. Nessuna configurazione è stata modificata.",
            "unknown": "La convalida non è riuscita in sicurezza. La configurazione esistente è rimasta invariata.",
            "qr_account_not_linked": "Nessun account Smart Life/Tuya tramite QR è collegato a questa voce LocalTuya. Inserisci manualmente la local key oppure ricollega l'account dalle opzioni LocalTuya.",
            "qr_reauth_required": "L'autorizzazione Tuya salvata è scaduta. Ricollega l'account Smart Life/Tuya e riprova.",
            "credential_refresh_failed": "LocalTuya non è riuscito a recuperare una local key utilizzabile dall'account Tuya collegato.",
            "init_title": "Ripara {device_name}",
            "init_description": "Scegli un'azione di recupero. LocalTuya verifica credenziali, protocollo e datapoint prima di salvare le modifiche.",
            "refresh_credentials": "Aggiorna la local key dall'account Tuya collegato",
            "manual_credentials": "Inserisci manualmente la local key",
            "select_protocol": "Seleziona la versione del protocollo",
            "retry": "Riprova la configurazione attuale",
            "retry_title": "Riprova {device_name}",
            "retry_description": "Convalida di nuovo indirizzo LAN, credenziali, protocollo e datapoint attualmente salvati senza modificarli prima.",
            "manual_title": "Aggiorna la local key di {device_name}",
            "manual_description": "Inserisci la local key attuale. Per un dispositivo figlio dietro gateway usa la local key del gateway. Viene salvata solo dopo una convalida LAN riuscita.",
            "local_key": "Chiave locale",
            "refresh_title": "Aggiorna la local key di {device_name}",
            "refresh_description": "Sincronizza su richiesta l'account Smart Life/Tuya collegato e verifica via LAN la nuova chiave prima di salvarla.",
            "protocol_title": "Seleziona il protocollo per {device_name}",
            "protocol_description": "Scegli Automatico o un protocollo Tuya LAN esplicito. LocalTuya convalida la scelta prima di salvarla.",
            "protocol_version": "Versione del protocollo",
        },
        "fallback_description": "Questa contribuzione è troppo grande per una precompilazione GitHub affidabile. Copia o controlla il JSON anonimizzato qui sotto, quindi scegli Invia al catalogo della community. File suggerito: `{filename}`. Nulla viene caricato automaticamente.",
    },
    "de": {
        "titles": {
            "device_health_host_unreachable": "LocalTuya kann {device_name} nicht erreichen",
            "device_health_auth_or_protocol": "LocalTuya kann {device_name} nicht authentifizieren",
            "device_health_protocol_not_detected": "LocalTuya konnte das Protokoll für {device_name} nicht erkennen",
            "device_health_empty_dps": "LocalTuya hat keine Datenpunkte von {device_name} erhalten",
            "device_health_invalid_configuration": "LocalTuya hat eine ungültige Konfiguration für {device_name} gefunden",
            "device_health_probe_error": "LocalTuya konnte die Zustandsprüfung für {device_name} nicht abschließen",
        },
        "descriptions": {
            "device_health_host_unreachable": "Das Gerät ist unter der gespeicherten LAN-Adresse nicht erreichbar. Gateway/Gerät erneut erkennen oder die aktuelle Adresse eingeben; LocalTuya prüft sie vor dem Speichern.",
            "device_health_auth_or_protocol": "Das LAN-Gerät antwortet, aber Authentifizierung oder Protokollprüfung schlägt fehl. Lokalen Schlüssel aktualisieren/eingeben, Protokoll wählen oder erneut versuchen.",
            "device_health_protocol_not_detected": "Die automatische Erkennung hat kein funktionierendes Tuya-LAN-Protokoll gefunden. Protokoll ausdrücklich auswählen oder erneut versuchen.",
            "device_health_empty_dps": "Das Gerät wurde authentifiziert, liefert aber keine Datenpunkte. Erneut versuchen oder das Protokoll ausdrücklich auswählen.",
            "device_health_invalid_configuration": "Die gespeicherte LocalTuya-Konfiguration kann nicht sicher validiert werden. Zugangsdaten/Protokoll prüfen oder ohne Verlust der aktuellen Konfiguration erneut versuchen.",
            "device_health_probe_error": "Die begrenzte LocalTuya-Zustandsprüfung ist unerwartet fehlgeschlagen. Aktuelle Konfiguration erneut versuchen oder Protokoll ausdrücklich auswählen.",
        },
        "host": {
            "cannot_connect": "Das Gerät antwortet unter dieser Adresse nicht. Prüfe, ob es eingeschaltet und von Home Assistant erreichbar ist.",
            "invalid_auth": "Das Gerät antwortet, lehnt aber die gespeicherten lokalen Zugangsdaten ab. Zugangsdaten aktualisieren oder neu konfigurieren.",
            "empty_dps": "Die Verbindung war erfolgreich, aber es wurden keine Datenpunkte zurückgegeben. Erneut versuchen, wenn das Gerät vollständig online ist.",
            "invalid_host": "Gib eine gültige LAN-IP-Adresse oder einen Hostnamen ein.",
            "unknown": "Die Adresse konnte nicht sicher validiert werden. Die bestehende Konfiguration wurde nicht geändert.",
            "stale": "Die Geräteadresse hat sich während der Prüfung erneut geändert. Erkennung wiederholen oder die aktuelle Adresse manuell eingeben.",
            "device_not_found": "Das konfigurierte Gerät wurde bei der LAN-Erkennung nicht gefunden. Die aktuelle Adresse kann manuell eingegeben werden.",
            "discovery_unavailable": "Die automatische LAN-Erkennung ist derzeit nicht verfügbar. Gib die Geräteadresse manuell ein.",
            "discovery_failed": "Die automatische LAN-Erkennung ist fehlgeschlagen. Geräteadresse manuell eingeben oder später erneut versuchen.",
            "init_title": "LAN-Verbindung für {device_name} reparieren",
            "init_description": "Automatische Neuerkennung wählen oder die aktuelle LAN-Adresse eingeben. LocalTuya validiert Geräte-ID, lokalen Schlüssel, Protokoll und Datenpunkte vor dem Speichern.",
            "rediscover": "Automatische LAN-Erkennung erneut versuchen",
            "manual_host": "IP-Adresse / Hostnamen manuell eingeben",
            "manual_title": "Aktuelle LAN-Adresse eingeben",
            "manual_description": "Gib die aktuelle IP-Adresse oder den Hostnamen für {device_name} ein. Die Adresse wird nur nach erfolgreicher authentifizierter LocalTuya-Prüfung gespeichert.",
            "host_label": "IP-Adresse / Host",
        },
        "device": {
            "abort_not_found": "Das konfigurierte Gerät existiert nicht mehr.",
            "cannot_connect": "Das Gerät konnte über LAN nicht erreicht werden. Die Konfiguration wurde nicht geändert.",
            "invalid_auth": "Das Gerät hat die gespeicherten Zugangsdaten abgelehnt. Die Konfiguration wurde nicht geändert.",
            "empty_dps": "Das Gerät verbindet sich, liefert aber keine Datenpunkte. Die Konfiguration wurde nicht geändert.",
            "unknown": "Die Validierung ist sicher fehlgeschlagen. Die bestehende Konfiguration blieb unverändert.",
            "qr_account_not_linked": "Mit diesem LocalTuya-Eintrag ist kein Smart-Life/Tuya-QR-Konto verknüpft. Lokalen Schlüssel manuell eingeben oder das Konto in den LocalTuya-Optionen neu verknüpfen.",
            "qr_reauth_required": "Die gespeicherte Tuya-Autorisierung ist abgelaufen. Smart-Life/Tuya-Konto neu verknüpfen und erneut versuchen.",
            "credential_refresh_failed": "LocalTuya konnte keinen verwendbaren lokalen Schlüssel aus dem verknüpften Tuya-Konto abrufen.",
            "init_title": "{device_name} reparieren",
            "init_description": "Wähle eine Wiederherstellungsaktion. LocalTuya prüft Zugangsdaten, Protokoll und Datenpunkte vor dem Speichern von Änderungen.",
            "refresh_credentials": "Lokalen Schlüssel aus verknüpftem Tuya-Konto aktualisieren",
            "manual_credentials": "Lokalen Schlüssel manuell eingeben",
            "select_protocol": "Protokollversion auswählen",
            "retry": "Aktuelle Konfiguration erneut versuchen",
            "retry_title": "{device_name} erneut prüfen",
            "retry_description": "Gespeicherte LAN-Adresse, Zugangsdaten, Protokoll und Datenpunkte erneut validieren, ohne sie vorher zu ändern.",
            "manual_title": "Lokalen Schlüssel für {device_name} aktualisieren",
            "manual_description": "Gib den aktuellen lokalen Schlüssel ein. Für ein Gateway-Untergerät den lokalen Gateway-Schlüssel verwenden. Er wird nur nach erfolgreicher LAN-Prüfung gespeichert.",
            "local_key": "Lokaler Schlüssel",
            "refresh_title": "Lokalen Schlüssel für {device_name} aktualisieren",
            "refresh_description": "Das verknüpfte Smart-Life/Tuya-Konto bei Bedarf synchronisieren und den aktualisierten Schlüssel vor dem Speichern über LAN prüfen.",
            "protocol_title": "Protokoll für {device_name} auswählen",
            "protocol_description": "Automatisch oder ein bestimmtes Tuya-LAN-Protokoll auswählen. LocalTuya validiert die Auswahl vor dem Speichern.",
            "protocol_version": "Protokollversion",
        },
        "fallback_description": "Dieser Beitrag ist für eine zuverlässige GitHub-Vorbelegung zu groß. Prüfe oder kopiere das bereinigte JSON unten und wähle anschließend An Community-Katalog senden. Vorgeschlagene Datei: `{filename}`. Es wird nichts automatisch hochgeladen.",
    },
    "pt-BR": {
        "titles": {
            "device_health_host_unreachable": "O LocalTuya não consegue acessar {device_name}",
            "device_health_auth_or_protocol": "O LocalTuya não consegue autenticar {device_name}",
            "device_health_protocol_not_detected": "O LocalTuya não detectou o protocolo de {device_name}",
            "device_health_empty_dps": "O LocalTuya não recebeu pontos de dados de {device_name}",
            "device_health_invalid_configuration": "O LocalTuya encontrou uma configuração inválida para {device_name}",
            "device_health_probe_error": "O LocalTuya não concluiu a verificação de {device_name}",
        },
        "descriptions": {
            "device_health_host_unreachable": "O dispositivo não está acessível no endereço LAN salvo. Redescubra o gateway/dispositivo ou informe o endereço atual; o LocalTuya valida antes de salvar.",
            "device_health_auth_or_protocol": "O dispositivo LAN respondeu, mas a autenticação ou o protocolo falhou. Atualize/informe a chave local, selecione o protocolo ou tente novamente.",
            "device_health_protocol_not_detected": "A detecção automática não encontrou um protocolo LAN Tuya funcional. Selecione um protocolo explicitamente ou tente novamente.",
            "device_health_empty_dps": "O dispositivo autenticou, mas não retornou pontos de dados. Tente novamente ou selecione explicitamente o protocolo antes de alterar a configuração.",
            "device_health_invalid_configuration": "A configuração LocalTuya salva não pode ser validada com segurança. Revise credenciais/protocolo ou tente novamente sem perder a configuração atual.",
            "device_health_probe_error": "A verificação limitada de integridade do LocalTuya falhou inesperadamente. Tente a configuração atual novamente ou selecione um protocolo.",
        },
        "host": {
            "cannot_connect": "O dispositivo não respondeu nesse endereço. Verifique se está ligado e acessível pelo Home Assistant.",
            "invalid_auth": "O dispositivo respondeu, mas rejeitou as credenciais locais salvas. Atualize ou reconfigure as credenciais antes de tentar novamente.",
            "empty_dps": "A conexão foi bem-sucedida, mas nenhum ponto de dados foi retornado. Tente novamente quando o dispositivo estiver totalmente online.",
            "invalid_host": "Informe um endereço IP LAN ou nome de host válido.",
            "unknown": "O endereço não pôde ser validado com segurança. A configuração existente não foi alterada.",
            "stale": "O endereço do dispositivo mudou novamente durante a validação. Repita a descoberta ou informe manualmente o endereço atual.",
            "device_not_found": "O dispositivo configurado não foi encontrado na descoberta LAN. Você pode informar manualmente o endereço atual.",
            "discovery_unavailable": "A descoberta LAN automática não está disponível agora. Informe manualmente o endereço do dispositivo.",
            "discovery_failed": "A descoberta LAN automática falhou. Informe manualmente o endereço ou tente novamente mais tarde.",
            "init_title": "Reparar conexão LAN de {device_name}",
            "init_description": "Escolha a redescoberta automática ou informe o endereço LAN atual. O LocalTuya valida ID do dispositivo, chave local, protocolo e pontos de dados antes de salvar.",
            "rediscover": "Tentar novamente a descoberta LAN automática",
            "manual_host": "Informar IP / nome de host manualmente",
            "manual_title": "Informar o endereço LAN atual",
            "manual_description": "Informe o endereço IP ou nome de host atual de {device_name}. Ele será salvo somente após uma validação LocalTuya autenticada bem-sucedida.",
            "host_label": "Endereço IP / Host",
        },
        "device": {
            "abort_not_found": "O dispositivo configurado não existe mais.",
            "cannot_connect": "O dispositivo não pôde ser acessado pela LAN. Nenhuma configuração foi alterada.",
            "invalid_auth": "O dispositivo rejeitou as credenciais salvas. Nenhuma configuração foi alterada.",
            "empty_dps": "O dispositivo conectou, mas não retornou pontos de dados. Nenhuma configuração foi alterada.",
            "unknown": "A validação falhou com segurança. A configuração existente permaneceu inalterada.",
            "qr_account_not_linked": "Nenhuma conta Smart Life/Tuya via QR está vinculada a esta entrada LocalTuya. Informe a chave local manualmente ou vincule a conta novamente nas opções.",
            "qr_reauth_required": "A autorização Tuya salva expirou. Vincule novamente a conta Smart Life/Tuya e tente de novo.",
            "credential_refresh_failed": "O LocalTuya não conseguiu obter uma chave local utilizável da conta Tuya vinculada.",
            "init_title": "Reparar {device_name}",
            "init_description": "Escolha uma ação de recuperação. O LocalTuya valida credenciais, protocolo e pontos de dados antes de salvar alterações.",
            "refresh_credentials": "Atualizar chave local pela conta Tuya vinculada",
            "manual_credentials": "Informar a chave local manualmente",
            "select_protocol": "Selecionar versão do protocolo",
            "retry": "Tentar novamente a configuração atual",
            "retry_title": "Tentar novamente {device_name}",
            "retry_description": "Validar novamente endereço LAN, credenciais, protocolo e pontos de dados salvos sem alterá-los primeiro.",
            "manual_title": "Atualizar a chave local de {device_name}",
            "manual_description": "Informe a chave local atual. Para um dispositivo filho de gateway, use a chave local do gateway. Ela só é salva após validação LAN bem-sucedida.",
            "local_key": "Chave local",
            "refresh_title": "Atualizar a chave local de {device_name}",
            "refresh_description": "Sincronize sob demanda a conta Smart Life/Tuya vinculada e valide a chave atualizada pela LAN antes de salvar.",
            "protocol_title": "Selecionar protocolo para {device_name}",
            "protocol_description": "Escolha Automático ou um protocolo LAN Tuya explícito. O LocalTuya valida a seleção antes de salvar.",
            "protocol_version": "Versão do protocolo",
        },
        "fallback_description": "Esta contribuição é grande demais para um preenchimento confiável no GitHub. Revise ou copie o JSON sanitizado abaixo e depois escolha Enviar ao catálogo da comunidade. Arquivo sugerido: `{filename}`. Nada é enviado automaticamente.",
    },
    "zh-Hans": {
        "titles": {
            "device_health_host_unreachable": "LocalTuya 无法连接 {device_name}",
            "device_health_auth_or_protocol": "LocalTuya 无法验证 {device_name}",
            "device_health_protocol_not_detected": "LocalTuya 无法检测 {device_name} 的协议",
            "device_health_empty_dps": "LocalTuya 未从 {device_name} 收到数据点",
            "device_health_invalid_configuration": "LocalTuya 检测到 {device_name} 的配置无效",
            "device_health_probe_error": "LocalTuya 无法完成 {device_name} 的健康检查",
        },
        "descriptions": {
            "device_health_host_unreachable": "设备无法通过已保存的局域网地址访问。请重新发现网关/设备或输入当前地址；LocalTuya 会先验证再保存。",
            "device_health_auth_or_protocol": "局域网设备有响应，但身份验证或协议验证失败。请刷新/输入本地密钥、选择协议或重试。",
            "device_health_protocol_not_detected": "自动检测未找到可用的 Tuya 局域网协议。请选择明确的协议版本或重试。",
            "device_health_empty_dps": "设备已通过身份验证，但没有返回数据点。请重试或明确选择协议后再修改配置。",
            "device_health_invalid_configuration": "已保存的 LocalTuya 配置无法安全验证。请检查凭据/协议，或在保留当前配置的情况下重试。",
            "device_health_probe_error": "LocalTuya 的限时健康检查意外失败。请重试当前配置或明确选择协议。",
        },
        "host": {
            "cannot_connect": "设备在该地址没有响应。请确认设备已开机并且 Home Assistant 可以访问它。",
            "invalid_auth": "设备有响应，但拒绝了已保存的本地凭据。请先刷新或重新配置凭据再重试。",
            "empty_dps": "连接成功，但设备没有返回任何数据点。请在设备完全在线后重试。",
            "invalid_host": "请输入有效的局域网 IP 地址或主机名。",
            "unknown": "无法安全验证该地址。现有配置保持不变。",
            "stale": "验证期间设备地址再次发生变化。请重新发现或手动输入当前地址。",
            "device_not_found": "局域网发现中未找到已配置设备。你可以手动输入它的当前地址。",
            "discovery_unavailable": "当前无法使用自动局域网发现。请手动输入设备地址。",
            "discovery_failed": "自动局域网发现失败。请手动输入设备地址或稍后重试。",
            "init_title": "修复 {device_name} 的局域网连接",
            "init_description": "请选择自动重新发现或输入设备当前的局域网地址。LocalTuya 会在保存新地址前验证设备 ID、本地密钥、协议和数据点。",
            "rediscover": "重新尝试自动局域网发现",
            "manual_host": "手动输入 IP 地址 / 主机名",
            "manual_title": "输入当前局域网地址",
            "manual_description": "请输入 {device_name} 当前的 IP 地址或主机名。只有通过 LocalTuya 身份验证后才会保存。",
            "host_label": "IP 地址 / 主机",
        },
        "device": {
            "abort_not_found": "已配置的设备已不存在。",
            "cannot_connect": "无法通过局域网访问设备。没有修改任何配置。",
            "invalid_auth": "设备拒绝了已保存的凭据。没有修改任何配置。",
            "empty_dps": "设备已连接，但没有返回数据点。没有修改任何配置。",
            "unknown": "验证安全失败。现有配置保持不变。",
            "qr_account_not_linked": "此 LocalTuya 条目没有关联 Smart Life/Tuya QR 账户。请手动输入本地密钥，或在 LocalTuya 选项中重新关联账户。",
            "qr_reauth_required": "已保存的 Tuya 授权已过期。请重新关联 Smart Life/Tuya 账户后重试。",
            "credential_refresh_failed": "LocalTuya 无法从已关联的 Tuya 账户获取可用的本地密钥。",
            "init_title": "修复 {device_name}",
            "init_description": "请选择恢复操作。LocalTuya 会在保存更改前验证凭据、协议和数据点。",
            "refresh_credentials": "从已关联的 Tuya 账户刷新本地密钥",
            "manual_credentials": "手动输入本地密钥",
            "select_protocol": "选择协议版本",
            "retry": "重试当前配置",
            "retry_title": "重试 {device_name}",
            "retry_description": "在不预先修改配置的情况下，再次验证已保存的局域网地址、凭据、协议和数据点。",
            "manual_title": "更新 {device_name} 的本地密钥",
            "manual_description": "请输入当前本地密钥。对于网关下的子设备，请使用网关本地密钥。只有局域网验证成功后才会保存。",
            "local_key": "本地密钥",
            "refresh_title": "刷新 {device_name} 的本地密钥",
            "refresh_description": "按需同步已关联的 Smart Life/Tuya 账户，并在保存前通过局域网验证刷新后的密钥。",
            "protocol_title": "为 {device_name} 选择协议",
            "protocol_description": "请选择自动或明确的 Tuya 局域网协议。LocalTuya 会先验证选择再保存。",
            "protocol_version": "协议版本",
        },
        "fallback_description": "此贡献内容过大，无法可靠地预填到 GitHub。请查看或复制下方已脱敏的 JSON，然后选择提交到社区目录。建议文件：`{filename}`。不会自动上传任何内容。",
    },
}


def host_issue(locale: dict, title: str, description: str) -> dict:
    h = locale["host"]
    return {
        "title": title,
        "fix_flow": {
            "error": {key: h[key] for key in (
                "cannot_connect", "invalid_auth", "empty_dps", "invalid_host",
                "unknown", "stale", "device_not_found", "discovery_unavailable",
                "discovery_failed",
            )},
            "step": {
                "init": {
                    "title": h["init_title"],
                    "description": description,
                    "menu_options": {
                        "rediscover": h["rediscover"],
                        "manual_host": h["manual_host"],
                    },
                },
                "manual_host": {
                    "title": h["manual_title"],
                    "description": h["manual_description"],
                    "data": {"host": h["host_label"]},
                },
            },
        },
    }


def device_issue(locale: dict, title: str, description: str) -> dict:
    d = locale["device"]
    return {
        "title": title,
        "fix_flow": {
            "abort": {"device_not_found": d["abort_not_found"]},
            "error": {key: d[key] for key in (
                "cannot_connect", "invalid_auth", "empty_dps", "unknown",
                "qr_account_not_linked", "qr_reauth_required",
                "credential_refresh_failed",
            )},
            "step": {
                "init": {
                    "title": d["init_title"],
                    "description": description,
                    "menu_options": {
                        "refresh_credentials": d["refresh_credentials"],
                        "manual_credentials": d["manual_credentials"],
                        "select_protocol": d["select_protocol"],
                        "retry": d["retry"],
                    },
                },
                "retry": {
                    "title": d["retry_title"],
                    "description": d["retry_description"],
                },
                "manual_credentials": {
                    "title": d["manual_title"],
                    "description": d["manual_description"],
                    "data": {"local_key": d["local_key"]},
                },
                "refresh_credentials": {
                    "title": d["refresh_title"],
                    "description": d["refresh_description"],
                },
                "select_protocol": {
                    "title": d["protocol_title"],
                    "description": d["protocol_description"],
                    "data": {"protocol_version": d["protocol_version"]},
                },
            },
        },
    }


for language, locale in TRANSLATION_DATA.items():
    path = Path(f"custom_components/localtuya/translations/{language}.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    issues = payload.setdefault("issues", {})
    key = "device_health_host_unreachable"
    issues[key] = host_issue(locale, locale["titles"][key], locale["descriptions"][key])
    for key in (
        "device_health_auth_or_protocol",
        "device_health_protocol_not_detected",
        "device_health_empty_dps",
        "device_health_invalid_configuration",
        "device_health_probe_error",
    ):
        issues[key] = device_issue(locale, locale["titles"][key], locale["descriptions"][key])
    payload["options"]["step"]["prepare_contribution_result"]["description"] = locale[
        "fallback_description"
    ]
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Regression tests for the repaired behavior.
# ---------------------------------------------------------------------------
path = Path("tests/test_gateway_shared_transport.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    async def test_parent_disconnect_notifies_all_children(self):\n        first_listener = FakeListener()\n        second_listener = FakeListener()\n        first = await self._acquire("child-1", "cid-1", first_listener)\n        await self._acquire("child-2", "cid-2", second_listener)\n\n        first._shared.parent_disconnected()\n        self.assertEqual(first_listener.disconnects, 1)\n        self.assertEqual(second_listener.disconnects, 1)\n\n\nif __name__ == "__main__":\n''',
    '''    async def test_parent_disconnect_notifies_all_children(self):\n        first_listener = FakeListener()\n        second_listener = FakeListener()\n        first = await self._acquire("child-1", "cid-1", first_listener)\n        await self._acquire("child-2", "cid-2", second_listener)\n\n        first._shared.parent_disconnected()\n        self.assertEqual(first_listener.disconnects, 1)\n        self.assertEqual(second_listener.disconnects, 1)\n\n    async def test_dead_transport_is_replaced_on_next_acquire(self):\n        first = await self._acquire("child-1", "cid-1", FakeListener())\n        first_shared = first._shared\n        second_parent = FakeParent()\n        self.connect.side_effect = [second_parent]\n\n        first_shared.parent_disconnected()\n        second = await self._acquire("child-2", "cid-2", FakeListener())\n\n        self.assertIsNot(second._shared, first_shared)\n        self.assertIs(second._shared.parent, second_parent)\n        self.assertEqual(self.connect.await_count, 2)\n        self.parent.close.assert_awaited_once()\n\n    async def test_heartbeat_failure_invalidates_and_notifies_children(self):\n        first_listener = FakeListener()\n        second_listener = FakeListener()\n        first = await self._acquire("child-1", "cid-1", first_listener)\n        await self._acquire("child-2", "cid-2", second_listener)\n        self.parent.heartbeat = AsyncMock(side_effect=TimeoutError())\n\n        await first._shared._heartbeat_loop()\n\n        self.assertFalse(first._shared.alive)\n        self.assertEqual(first_listener.disconnects, 1)\n        self.assertEqual(second_listener.disconnects, 1)\n        self.parent.transport.close.assert_called_once()\n\n\nif __name__ == "__main__":\n''',
    "gateway regression tests",
)
path.write_text(text, encoding="utf-8")

path = Path("tests/test_qr_import_onboarding.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    def test_tinytuya_aliases_are_supported(self):\n        devices = _parse_import_payload(json.dumps([{"id": "device-b", "key": "secret-b", "ip": "192.168.1.31", "version": "3.3", "name": "Desk Lamp"}]))\n        self.assertEqual(devices["device-b"]["host"], "192.168.1.31")\n        self.assertEqual(devices["device-b"]["protocol_version"], "3.3")\n\nclass QrImportFlowTests''',
    '''    def test_tinytuya_aliases_are_supported(self):\n        devices = _parse_import_payload(json.dumps([{"id": "device-b", "key": "secret-b", "ip": "192.168.1.31", "version": "3.3", "name": "Desk Lamp"}]))\n        self.assertEqual(devices["device-b"]["host"], "192.168.1.31")\n        self.assertEqual(devices["device-b"]["protocol_version"], "3.3")\n\n    def test_gateway_routing_metadata_is_preserved(self):\n        devices = _parse_import_payload(json.dumps({\n            "id": "child-1", "key": "gateway-key", "gateway_id": "gateway-1",\n            "node_id": "node-1",\n        }))\n        self.assertEqual(devices["child-1"]["gateway_id"], "gateway-1")\n        self.assertEqual(devices["child-1"]["node_id"], "node-1")\n\n    def test_true_subdevice_uses_uuid_as_cid_but_string_false_does_not(self):\n        true_child = _parse_import_payload(json.dumps({\n            "id": "child-true", "key": "gateway-key", "gateway_id": "gateway-1",\n            "sub": True, "uuid": "uuid-cid",\n        }))["child-true"]\n        false_child = _parse_import_payload(json.dumps({\n            "id": "child-false", "key": "gateway-key", "gateway_id": "gateway-1",\n            "sub": "false", "uuid": "must-not-be-cid",\n        }))["child-false"]\n        self.assertEqual(true_child["node_id"], "uuid-cid")\n        self.assertNotIn("node_id", false_child)\n\nclass QrImportFlowTests''',
    "QR import routing tests",
)
path.write_text(text, encoding="utf-8")

path = Path("tests/test_mapping_export.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        self.assertEqual(query["filename"], [package["suggested_filename"]])\n        self.assertEqual(query["value"], [package["submission_json"]])\n        self.assertFalse(package["privacy"]["automatic_upload"])\n''',
    '''        self.assertEqual(query["filename"], [package["suggested_filename"]])\n        self.assertEqual(json.loads(query["value"][0]), package["submission"])\n        self.assertTrue(package["prefill_complete"])\n        self.assertFalse(package["privacy"]["automatic_upload"])\n''',
    "compact contribution prefill test",
)
text = replace_once(
    text,
    '''        self.assertEqual(query["filename"], [package["suggested_filename"]])\n        self.assertNotIn("value", query)\n''',
    '''        self.assertEqual(query["filename"], [package["suggested_filename"]])\n        self.assertNotIn("value", query)\n        self.assertFalse(package["prefill_complete"])\n''',
    "large contribution fallback test",
)
path.write_text(text, encoding="utf-8")

path = Path("tests/test_repairs.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    def __init__(self, entries):\n        self._entries = list(entries)\n\n    def async_entries(self, domain=None):\n        if domain is not None and domain != DOMAIN:\n            return []\n        return list(self._entries)\n''',
    '''    def __init__(self, entries):\n        self._entries = list(entries)\n        self.reload_calls = []\n\n    def async_entries(self, domain=None):\n        if domain is not None and domain != DOMAIN:\n            return []\n        return list(self._entries)\n\n    def async_update_entry(self, entry, *, data):\n        entry.data = data\n\n    async def async_reload(self, entry_id):\n        self.reload_calls.append(entry_id)\n        return True\n''',
    "repair fake config entries",
)
text = replace_once(
    text,
    '''from custom_components.localtuya.const import (\n    CONF_LOCAL_KEY,\n    CONF_PROTOCOL_VERSION,\n    DATA_DISCOVERY,\n    DOMAIN,\n)\n''',
    '''from custom_components.localtuya.const import (\n    ATTR_UPDATED_AT,\n    CONF_DPS_STRINGS,\n    CONF_LOCAL_KEY,\n    CONF_PROTOCOL_VERSION,\n    DATA_DISCOVERY,\n    DOMAIN,\n)\n''',
    "repair test const imports",
)
text = replace_once(
    text,
    '''from custom_components.localtuya.repair_issues import host_recovery_issue_id\nfrom custom_components.localtuya.repairs import (\n    HostRecoveryRepairFlow,\n''',
    '''from custom_components.localtuya.qr_onboarding import CONF_QR_AUTH\nfrom custom_components.localtuya.repair_issues import (\n    device_health_issue_id,\n    host_recovery_issue_id,\n)\nfrom custom_components.localtuya.repairs import (\n    DeviceHealthRepairFlow,\n    HostRecoveryRepairFlow,\n''',
    "repair test imports",
)
text = replace_once(
    text,
    '''    async def test_unknown_issue_uses_safe_fallback_flow(self):\n        flow = await async_create_fix_flow(self.hass, "other_issue", None)\n\n        self.assertIsInstance(flow, ConfirmRepairFlow)\n\n    async def test_changed_host_is_applied_only_through_validated_recovery(self):\n''',
    '''    async def test_unknown_issue_uses_safe_fallback_flow(self):\n        flow = await async_create_fix_flow(self.hass, "other_issue", None)\n\n        self.assertIsInstance(flow, ConfirmRepairFlow)\n\n    async def test_device_health_issue_routes_to_device_repair_flow(self):\n        flow = await async_create_fix_flow(\n            self.hass,\n            device_health_issue_id(self.device_id, "auth_or_protocol"),\n            None,\n        )\n        self.assertIsInstance(flow, DeviceHealthRepairFlow)\n        flow.hass = self.hass\n        result = await flow.async_step_init()\n        self.assertEqual(\n            result["menu_options"],\n            ["refresh_credentials", "manual_credentials", "select_protocol", "retry"],\n        )\n\n    async def test_host_unreachable_health_issue_routes_to_host_repair(self):\n        flow = await async_create_fix_flow(\n            self.hass,\n            device_health_issue_id(self.device_id, "host_unreachable"),\n            None,\n        )\n        self.assertIsInstance(flow, HostRecoveryRepairFlow)\n\n    async def test_retry_persists_only_after_validation_and_reloads(self):\n        target = _find_repair_target(\n            self.hass,\n            device_health_issue_id(self.device_id, "auth_or_protocol"),\n        )\n        flow = DeviceHealthRepairFlow(target)\n        flow.hass = self.hass\n        with (\n            patch(\n                "custom_components.localtuya.repairs.validate_input",\n                new=AsyncMock(return_value=(["1 (value: True)"], "3.4")),\n            ),\n            patch("custom_components.localtuya.repairs.async_clear_device_health_issues"),\n            patch("custom_components.localtuya.repairs.async_clear_host_recovery_issue"),\n        ):\n            result = await flow.async_step_retry()\n        self.assertEqual(result["type"].value, "create_entry")\n        saved = self.entry.data[CONF_DEVICES][self.device_id]\n        self.assertEqual(saved[CONF_PROTOCOL_VERSION], "3.4")\n        self.assertEqual(saved[CONF_DPS_STRINGS], ["1 (value: True)"])\n        self.assertGreater(int(self.entry.data[ATTR_UPDATED_AT]), 1_000_000_000_000)\n        self.assertEqual(self.hass.config_entries.reload_calls, ["entry-1"])\n\n    async def test_failed_manual_key_never_overwrites_saved_key(self):\n        target = _find_repair_target(\n            self.hass,\n            device_health_issue_id(self.device_id, "auth_or_protocol"),\n        )\n        flow = DeviceHealthRepairFlow(target)\n        flow.hass = self.hass\n        from custom_components.localtuya.config_flow import InvalidAuth\n        with patch(\n            "custom_components.localtuya.repairs.validate_input",\n            new=AsyncMock(side_effect=InvalidAuth()),\n        ):\n            result = await flow.async_step_manual_credentials(\n                {CONF_LOCAL_KEY: "wrong-new-key"}\n            )\n        self.assertEqual(result["errors"], {"base": "invalid_auth"})\n        self.assertEqual(\n            self.entry.data[CONF_DEVICES][self.device_id][CONF_LOCAL_KEY],\n            "private-key",\n        )\n\n    async def test_qr_refresh_for_child_uses_gateway_key(self):\n        self.entry.data[CONF_QR_AUTH] = {"saved": "auth"}\n        child = self.entry.data[CONF_DEVICES][self.device_id]\n        child["node_id"] = "node-1"\n        child["gateway_id"] = "gateway-1"\n        target = _find_repair_target(\n            self.hass,\n            device_health_issue_id(self.device_id, "auth_or_protocol"),\n        )\n        flow = DeviceHealthRepairFlow(target)\n        flow.hass = self.hass\n        fake_client = SimpleNamespace(\n            async_get_devices=AsyncMock(return_value={\n                self.device_id: {\n                    "gateway_local_key": "fresh-gateway-key",\n                    CONF_LOCAL_KEY: "child-key-must-not-win",\n                }\n            }),\n            auth={"refreshed": "auth"},\n        )\n        with (\n            patch("custom_components.localtuya.repairs.QrCloudClient", return_value=fake_client),\n            patch(\n                "custom_components.localtuya.repairs.validate_input",\n                new=AsyncMock(return_value=(["20 (value: True)"], "3.4")),\n            ) as validator,\n            patch("custom_components.localtuya.repairs.async_clear_device_health_issues"),\n            patch("custom_components.localtuya.repairs.async_clear_host_recovery_issue"),\n        ):\n            result = await flow.async_step_refresh_credentials()\n        self.assertEqual(result["type"].value, "create_entry")\n        saved = self.entry.data[CONF_DEVICES][self.device_id]\n        self.assertEqual(saved[CONF_LOCAL_KEY], "fresh-gateway-key")\n        self.assertEqual(self.entry.data[CONF_QR_AUTH], {"refreshed": "auth"})\n        self.assertEqual(validator.await_args.args[1][CONF_LOCAL_KEY], "fresh-gateway-key")\n\n    async def test_changed_host_is_applied_only_through_validated_recovery(self):\n''',
    "device health repair tests",
)
path.write_text(text, encoding="utf-8")

path = Path("tests/test_repair_issues.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''from custom_components.localtuya.repair_issues import (\n    async_clear_host_recovery_issue,\n    async_sync_host_recovery_issue,\n    host_recovery_issue_id,\n)\n''',
    '''from custom_components.localtuya.device_health import (\n    DeviceHealthFailure,\n    DeviceHealthReport,\n    DeviceHealthStage,\n)\nfrom custom_components.localtuya.repair_issues import (\n    async_clear_host_recovery_issue,\n    async_sync_device_health_issue,\n    async_sync_host_recovery_issue,\n    device_health_issue_id,\n    host_recovery_issue_id,\n)\n''',
    "health repair issue imports",
)
text = replace_once(
    text,
    '''    @patch("custom_components.localtuya.repair_issues.ir.async_delete_issue")\n    def test_explicit_clear_uses_hashed_issue_id(self, delete_issue):\n''',
    '''    @patch("custom_components.localtuya.repair_issues.ir.async_delete_issue")\n    @patch("custom_components.localtuya.repair_issues.ir.async_create_issue")\n    def test_health_failure_creates_specific_private_fixable_issue(\n        self, create_issue, delete_issue\n    ):\n        hass = object()\n        device_id = "private-health-device"\n        report = DeviceHealthReport(\n            requested_protocol="auto",\n            stage=DeviceHealthStage.PROTOCOL,\n            failure=DeviceHealthFailure.AUTH_OR_PROTOCOL,\n        )\n        async_sync_device_health_issue(\n            hass, device_id=device_id, device_name="Bedroom lamp", report=report\n        )\n        self.assertTrue(delete_issue.called)\n        create_issue.assert_called_once()\n        args = create_issue.call_args.args\n        kwargs = create_issue.call_args.kwargs\n        self.assertEqual(args[2], device_health_issue_id(device_id, "auth_or_protocol"))\n        self.assertNotIn(device_id, args[2])\n        self.assertTrue(kwargs["is_fixable"])\n        self.assertEqual(kwargs["translation_key"], "device_health_auth_or_protocol")\n\n    @patch("custom_components.localtuya.repair_issues.ir.async_delete_issue")\n    def test_explicit_clear_uses_hashed_issue_id(self, delete_issue):\n''',
    "health repair issue test",
)
path.write_text(text, encoding="utf-8")

path = Path("tests/test_translation_coverage.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    def test_supported_languages_have_all_keys(\n        self,\n    ):\n''',
    '''    def test_device_health_repair_translation_contract(self):\n        issues = self.english.get("issues", {})\n        expected = {\n            "device_health_host_unreachable",\n            "device_health_auth_or_protocol",\n            "device_health_protocol_not_detected",\n            "device_health_empty_dps",\n            "device_health_invalid_configuration",\n            "device_health_probe_error",\n        }\n        self.assertTrue(expected.issubset(issues))\n        host_steps = issues["device_health_host_unreachable"]["fix_flow"]["step"]\n        self.assertEqual(set(host_steps), {"init", "manual_host"})\n        for key in expected - {"device_health_host_unreachable"}:\n            fix_flow = issues[key]["fix_flow"]\n            self.assertEqual(\n                set(fix_flow["step"]),\n                {"init", "retry", "manual_credentials", "refresh_credentials", "select_protocol"},\n            )\n            self.assertEqual(\n                set(fix_flow["step"]["init"]["menu_options"]),\n                {"refresh_credentials", "manual_credentials", "select_protocol", "retry"},\n            )\n            self.assertIn("device_not_found", fix_flow["abort"])\n\n    def test_supported_languages_have_all_keys(\n        self,\n    ):\n''',
    "translation health repair contract",
)
path.write_text(text, encoding="utf-8")

print("Roadmap 3/4/6/8 final hardening patch applied")

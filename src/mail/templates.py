"""Transactional email templates for the eight product locales (W12.4C).

Plain text only, assembled from fixed strings plus ONE server-built link: no candidate-authored text and no HTML are ever
interpolated, so there is nothing to inject into. The recipient's interface language is used when it is a supported product
locale, otherwise English. The brand line "Ask More. Be More." is a protected invariant and is never translated. The links
always end in ``?token=<opaque>``. These are engineering translations pending native review (same status as the interface
catalogues). Expiry text is derived from the configured token lifetimes, never hard-coded in the copy.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.locales import SUPPORTED_LOCALE_CODES

BRAND_LINE = "Ask More. Be More."
KINDS = ("email_verification", "password_reset", "account_notice", "admin_test", "workspace_invitation", "ownership_transfer")


@dataclass(frozen=True)
class Rendered:
    subject: str
    body: str
    locale: str


# {link} {expiry} are the only placeholders. "{expiry}" is a localised duration phrase built by _duration().
_T: dict[str, dict[str, dict[str, str]]] = {
    "en": {
        "email_verification": {"subject": "Verify your Ask4Mo email", "body": "Welcome to Ask4Mo. Verify your email:\n{link}\n\nThis link expires in {expiry}. If you did not create an account, you can ignore this email."},
        "password_reset": {"subject": "Reset your Ask4Mo password", "body": "Reset your password:\n{link}\n\nThis link expires in {expiry}. If you did not request this, ignore this email; your password stays unchanged."},
        "account_notice": {"subject": "Your Ask4Mo account", "body": "Someone tried to create an Ask4Mo account with this email, but one already exists. If this was you, please sign in or reset your password."},
        "admin_test": {"subject": "Ask4Mo email delivery test", "body": "This is a test message requested by an Ask4Mo administrator to check email delivery. No action is needed."},
    },
    "de": {
        "email_verification": {"subject": "Bestätige deine Ask4Mo-E-Mail-Adresse", "body": "Willkommen bei Ask4Mo. Bestätige deine E-Mail-Adresse:\n{link}\n\nDieser Link läuft in {expiry} ab. Wenn du kein Konto erstellt hast, kannst du diese E-Mail ignorieren."},
        "password_reset": {"subject": "Setze dein Ask4Mo-Passwort zurück", "body": "Setze dein Passwort zurück:\n{link}\n\nDieser Link läuft in {expiry} ab. Wenn du das nicht angefordert hast, ignoriere diese E-Mail; dein Passwort bleibt unverändert."},
        "account_notice": {"subject": "Dein Ask4Mo-Konto", "body": "Jemand hat versucht, mit dieser E-Mail-Adresse ein Ask4Mo-Konto zu erstellen, aber es existiert bereits eines. Wenn du das warst, melde dich an oder setze dein Passwort zurück."},
        "admin_test": {"subject": "Ask4Mo-Test der E-Mail-Zustellung", "body": "Dies ist eine Testnachricht, die ein Ask4Mo-Administrator angefordert hat, um die E-Mail-Zustellung zu prüfen. Es ist nichts zu tun."},
    },
    "fr": {
        "email_verification": {"subject": "Vérifiez votre adresse e-mail Ask4Mo", "body": "Bienvenue sur Ask4Mo. Vérifiez votre adresse e-mail :\n{link}\n\nCe lien expire dans {expiry}. Si vous n'avez pas créé de compte, vous pouvez ignorer cet e-mail."},
        "password_reset": {"subject": "Réinitialisez votre mot de passe Ask4Mo", "body": "Réinitialisez votre mot de passe :\n{link}\n\nCe lien expire dans {expiry}. Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail ; votre mot de passe reste inchangé."},
        "account_notice": {"subject": "Votre compte Ask4Mo", "body": "Quelqu'un a essayé de créer un compte Ask4Mo avec cette adresse e-mail, mais un compte existe déjà. Si c'était vous, connectez-vous ou réinitialisez votre mot de passe."},
        "admin_test": {"subject": "Test de distribution des e-mails Ask4Mo", "body": "Ceci est un message de test demandé par un administrateur Ask4Mo pour vérifier la distribution des e-mails. Aucune action n'est nécessaire."},
    },
    "es": {
        "email_verification": {"subject": "Verifica tu correo de Ask4Mo", "body": "Te damos la bienvenida a Ask4Mo. Verifica tu correo electrónico:\n{link}\n\nEste enlace caduca en {expiry}. Si no creaste una cuenta, puedes ignorar este mensaje."},
        "password_reset": {"subject": "Restablece tu contraseña de Ask4Mo", "body": "Restablece tu contraseña:\n{link}\n\nEste enlace caduca en {expiry}. Si no lo solicitaste, ignora este mensaje; tu contraseña no cambiará."},
        "account_notice": {"subject": "Tu cuenta de Ask4Mo", "body": "Alguien intentó crear una cuenta de Ask4Mo con este correo, pero ya existe una. Si fuiste tú, inicia sesión o restablece tu contraseña."},
        "admin_test": {"subject": "Prueba de entrega de correo de Ask4Mo", "body": "Este es un mensaje de prueba solicitado por un administrador de Ask4Mo para comprobar la entrega de correo. No es necesario hacer nada."},
    },
    "it": {
        "email_verification": {"subject": "Verifica la tua email Ask4Mo", "body": "Benvenuto in Ask4Mo. Verifica il tuo indirizzo email:\n{link}\n\nQuesto link scade tra {expiry}. Se non hai creato un account, puoi ignorare questa email."},
        "password_reset": {"subject": "Reimposta la tua password Ask4Mo", "body": "Reimposta la tua password:\n{link}\n\nQuesto link scade tra {expiry}. Se non l'hai richiesto, ignora questa email; la tua password resta invariata."},
        "account_notice": {"subject": "Il tuo account Ask4Mo", "body": "Qualcuno ha provato a creare un account Ask4Mo con questa email, ma ne esiste già uno. Se eri tu, accedi o reimposta la password."},
        "admin_test": {"subject": "Test di consegna email Ask4Mo", "body": "Questo è un messaggio di prova richiesto da un amministratore Ask4Mo per verificare la consegna delle email. Non è necessaria alcuna azione."},
    },
    "pt": {
        "email_verification": {"subject": "Confirme o seu e-mail do Ask4Mo", "body": "Bem-vindo ao Ask4Mo. Confirme o seu e-mail:\n{link}\n\nEste link expira em {expiry}. Se não criou uma conta, pode ignorar este e-mail."},
        "password_reset": {"subject": "Redefina a sua palavra-passe do Ask4Mo", "body": "Redefina a sua palavra-passe:\n{link}\n\nEste link expira em {expiry}. Se não fez este pedido, ignore este e-mail; a sua palavra-passe não será alterada."},
        "account_notice": {"subject": "A sua conta Ask4Mo", "body": "Alguém tentou criar uma conta Ask4Mo com este e-mail, mas já existe uma. Se foi você, inicie sessão ou redefina a palavra-passe."},
        "admin_test": {"subject": "Teste de entrega de e-mail do Ask4Mo", "body": "Esta é uma mensagem de teste pedida por um administrador do Ask4Mo para verificar a entrega de e-mail. Não é necessária nenhuma ação."},
    },
    "nl": {
        "email_verification": {"subject": "Bevestig je Ask4Mo-e-mailadres", "body": "Welkom bij Ask4Mo. Bevestig je e-mailadres:\n{link}\n\nDeze link verloopt over {expiry}. Als je geen account hebt aangemaakt, kun je deze e-mail negeren."},
        "password_reset": {"subject": "Stel je Ask4Mo-wachtwoord opnieuw in", "body": "Stel je wachtwoord opnieuw in:\n{link}\n\nDeze link verloopt over {expiry}. Als je dit niet hebt aangevraagd, negeer deze e-mail dan; je wachtwoord blijft ongewijzigd."},
        "account_notice": {"subject": "Je Ask4Mo-account", "body": "Iemand probeerde met dit e-mailadres een Ask4Mo-account aan te maken, maar er bestaat er al een. Was jij het, log dan in of stel je wachtwoord opnieuw in."},
        "admin_test": {"subject": "Ask4Mo-test van e-mailbezorging", "body": "Dit is een testbericht dat een Ask4Mo-beheerder heeft aangevraagd om de e-mailbezorging te controleren. Er is geen actie nodig."},
    },
    "ru": {
        "email_verification": {"subject": "Подтвердите адрес электронной почты Ask4Mo", "body": "Добро пожаловать в Ask4Mo. Подтвердите адрес электронной почты:\n{link}\n\nСсылка действует {expiry}. Если вы не создавали учётную запись, просто проигнорируйте это письмо."},
        "password_reset": {"subject": "Сброс пароля Ask4Mo", "body": "Сбросьте пароль:\n{link}\n\nСсылка действует {expiry}. Если вы не запрашивали сброс, проигнорируйте это письмо; пароль не изменится."},
        "account_notice": {"subject": "Ваша учётная запись Ask4Mo", "body": "Кто-то пытался создать учётную запись Ask4Mo с этим адресом, но она уже существует. Если это были вы, войдите или сбросьте пароль."},
        "admin_test": {"subject": "Проверка доставки почты Ask4Mo", "body": "Это тестовое сообщение, запрошенное администратором Ask4Mo для проверки доставки почты. Никаких действий не требуется."},
    },
}

# 04B: the workspace invitation. Deliberately generic: it never interpolates the workspace name or the inviter's name (both are
# user-authored text, so they could carry a phishing message); the invited person sees the workspace name only after signing in
# with the invited address. {link} and {expiry} are the only placeholders.
_WORKSPACE_INVITATION: dict[str, dict[str, str]] = {
    "en": {"subject": "You have been invited to an Ask4Mo workspace", "body": "You have been invited to join a workspace on Ask4Mo. Joining shares nothing: only items you explicitly choose to share are ever visible to other members.\n\nReview the invitation:\n{link}\n\nThis invitation can be used once and expires in {expiry}. Sign in with this email address to accept or decline. If you did not expect it, ignore this email."},
    "de": {"subject": "Du wurdest zu einem Ask4Mo-Arbeitsbereich eingeladen", "body": "Du wurdest eingeladen, einem Arbeitsbereich bei Ask4Mo beizutreten. Der Beitritt teilt nichts: Andere Mitglieder sehen nur Inhalte, die du ausdrücklich teilst.\n\nEinladung ansehen:\n{link}\n\nDie Einladung kann einmal verwendet werden und läuft in {expiry} ab. Melde dich mit dieser E-Mail-Adresse an, um sie anzunehmen oder abzulehnen. Wenn du sie nicht erwartet hast, ignoriere diese E-Mail."},
    "fr": {"subject": "Vous avez été invité à un espace de travail Ask4Mo", "body": "Vous avez été invité à rejoindre un espace de travail sur Ask4Mo. Rejoindre ne partage rien : les autres membres ne voient que les éléments que vous choisissez explicitement de partager.\n\nConsulter l'invitation :\n{link}\n\nCette invitation n'est utilisable qu'une fois et expire dans {expiry}. Connectez-vous avec cette adresse e-mail pour l'accepter ou la refuser. Si vous ne l'attendiez pas, ignorez cet e-mail."},
    "es": {"subject": "Te han invitado a un espacio de trabajo de Ask4Mo", "body": "Te han invitado a unirte a un espacio de trabajo en Ask4Mo. Unirte no comparte nada: los demás miembros solo ven los elementos que decidas compartir de forma explícita.\n\nRevisa la invitación:\n{link}\n\nLa invitación se puede usar una vez y caduca en {expiry}. Inicia sesión con este correo para aceptarla o rechazarla. Si no la esperabas, ignora este mensaje."},
    "it": {"subject": "Sei stato invitato a uno spazio di lavoro Ask4Mo", "body": "Sei stato invitato a unirti a uno spazio di lavoro su Ask4Mo. Unirti non condivide nulla: gli altri membri vedono solo gli elementi che scegli esplicitamente di condividere.\n\nConsulta l'invito:\n{link}\n\nL'invito può essere usato una sola volta e scade tra {expiry}. Accedi con questo indirizzo email per accettarlo o rifiutarlo. Se non te lo aspettavi, ignora questa email."},
    "pt": {"subject": "Foi convidado para um espaço de trabalho do Ask4Mo", "body": "Foi convidado para se juntar a um espaço de trabalho no Ask4Mo. Juntar-se não partilha nada: os outros membros só veem os itens que escolher partilhar explicitamente.\n\nVeja o convite:\n{link}\n\nO convite pode ser usado uma vez e expira em {expiry}. Inicie sessão com este e-mail para aceitar ou recusar. Se não o esperava, ignore este e-mail."},
    "nl": {"subject": "Je bent uitgenodigd voor een Ask4Mo-werkruimte", "body": "Je bent uitgenodigd om lid te worden van een werkruimte op Ask4Mo. Lid worden deelt niets: andere leden zien alleen items die jij uitdrukkelijk kiest te delen.\n\nBekijk de uitnodiging:\n{link}\n\nDe uitnodiging kan één keer worden gebruikt en verloopt over {expiry}. Log in met dit e-mailadres om te accepteren of te weigeren. Als je dit niet verwachtte, negeer deze e-mail dan."},
    "ru": {"subject": "Вас пригласили в рабочее пространство Ask4Mo", "body": "Вас пригласили присоединиться к рабочему пространству в Ask4Mo. Присоединение ничего не раскрывает: другие участники видят только то, чем вы решили поделиться явно.\n\nПосмотреть приглашение:\n{link}\n\nПриглашение можно использовать один раз, оно действует {expiry}. Войдите с этим адресом электронной почты, чтобы принять или отклонить его. Если вы его не ждали, проигнорируйте это письмо."},
}
for _loc, _texts in _WORKSPACE_INVITATION.items():
    _T[_loc]["workspace_invitation"] = _texts

# 04B: the ownership-transfer notice. Generic like the invitation: no workspace name, no proposer name. The recipient must sign in with this address and
# accept; nothing changes before that. {link} and {expiry} are the only placeholders. Engineering translations (native review is a later gate).
_OWNERSHIP_TRANSFER: dict[str, dict[str, str]] = {
    "en": {"subject": "An Ask4Mo workspace owner proposed to transfer ownership to you", "body": "The owner of a workspace on Ask4Mo proposed to transfer ownership of it to you. Nothing changes unless you accept: sign in with this email address to review and accept or decline.\n\nReview the proposal:\n{link}\n\nThe proposal can be used once and is valid for {expiry}. If you did not expect it, ignore this email or decline it after signing in."},
    "de": {"subject": "Der Inhaber eines Ask4Mo-Arbeitsbereichs möchte dir die Inhaberschaft übertragen", "body": "Der Inhaber eines Arbeitsbereichs bei Ask4Mo möchte dir die Inhaberschaft übertragen. Es ändert sich nichts, solange du nicht zustimmst: Melde dich mit dieser E-Mail-Adresse an, um den Vorschlag zu prüfen und anzunehmen oder abzulehnen.\n\nVorschlag prüfen:\n{link}\n\nDer Vorschlag kann einmal verwendet werden und ist {expiry} gültig. Wenn du ihn nicht erwartet hast, ignoriere diese E-Mail oder lehne ihn nach der Anmeldung ab."},
    "fr": {"subject": "Le propriétaire d'un espace de travail Ask4Mo vous propose de vous transférer la propriété", "body": "Le propriétaire d'un espace de travail sur Ask4Mo vous propose de vous en transférer la propriété. Rien ne change tant que vous n'acceptez pas : connectez-vous avec cette adresse e-mail pour examiner la proposition, l'accepter ou la refuser.\n\nExaminer la proposition :\n{link}\n\nLa proposition ne peut être utilisée qu'une fois et reste valable {expiry}. Si vous ne l'attendiez pas, ignorez cet e-mail ou refusez-la après connexion."},
    "es": {"subject": "El propietario de un espacio de trabajo de Ask4Mo propone transferirte la propiedad", "body": "El propietario de un espacio de trabajo en Ask4Mo propone transferirte su propiedad. No cambia nada hasta que aceptes: inicia sesión con este correo electrónico para revisar la propuesta y aceptarla o rechazarla.\n\nRevisar la propuesta:\n{link}\n\nLa propuesta se puede usar una sola vez y es válida durante {expiry}. Si no la esperabas, ignora este mensaje o recházala después de iniciar sesión."},
    "it": {"subject": "Il proprietario di uno spazio di lavoro Ask4Mo propone di trasferirti la proprietà", "body": "Il proprietario di uno spazio di lavoro su Ask4Mo propone di trasferirti la proprietà. Non cambia nulla finché non accetti: accedi con questo indirizzo email per esaminare la proposta e accettarla o rifiutarla.\n\nEsamina la proposta:\n{link}\n\nLa proposta può essere usata una sola volta ed è valida per {expiry}. Se non te l'aspettavi, ignora questa email oppure rifiutala dopo l'accesso."},
    "pt": {"subject": "O proprietário de um espaço de trabalho do Ask4Mo propõe transferir-lhe a propriedade", "body": "O proprietário de um espaço de trabalho no Ask4Mo propõe transferir-lhe a propriedade. Nada muda enquanto não aceitar: inicie sessão com este endereço de email para analisar a proposta e aceitá-la ou recusá-la.\n\nAnalisar a proposta:\n{link}\n\nA proposta só pode ser usada uma vez e é válida durante {expiry}. Se não a esperava, ignore este email ou recuse-a depois de iniciar sessão."},
    "nl": {"subject": "De eigenaar van een Ask4Mo-werkruimte stelt voor het eigendom aan jou over te dragen", "body": "De eigenaar van een werkruimte op Ask4Mo stelt voor het eigendom aan jou over te dragen. Er verandert niets zolang je niet accepteert: log in met dit e-mailadres om het voorstel te bekijken en te accepteren of te weigeren.\n\nBekijk het voorstel:\n{link}\n\nHet voorstel kan één keer worden gebruikt en is {expiry} geldig. Als je het niet verwachtte, negeer dan deze e-mail of weiger het na het inloggen."},
    "ru": {"subject": "Владелец рабочего пространства Ask4Mo предлагает передать вам право владения", "body": "Владелец рабочего пространства в Ask4Mo предлагает передать вам право владения им. Ничего не изменится, пока вы не согласитесь: войдите с этим адресом электронной почты, чтобы рассмотреть предложение и принять или отклонить его.\n\nРассмотреть предложение:\n{link}\n\nПредложением можно воспользоваться один раз, оно действует {expiry}. Если вы его не ждали, проигнорируйте это письмо или отклоните предложение после входа."},
}
for _loc, _texts in _OWNERSHIP_TRANSFER.items():
    _T[_loc]["ownership_transfer"] = _texts

# Localised duration phrases for the two token lifetimes (hours / minutes). Anything else falls back to hours.
_HOURS = {
    "en": lambda n: f"{n} hour" + ("" if n == 1 else "s"), "de": lambda n: f"{n} Stunde" + ("" if n == 1 else "n"),
    "fr": lambda n: f"{n} heure" + ("" if n == 1 else "s"), "es": lambda n: f"{n} hora" + ("" if n == 1 else "s"),
    "it": lambda n: f"{n} or" + ("a" if n == 1 else "e"), "pt": lambda n: f"{n} hora" + ("" if n == 1 else "s"),
    "nl": lambda n: f"{n} uur", "ru": lambda n: f"{n} " + ("час" if n % 10 == 1 and n % 100 != 11 else "часа" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "часов"),
}
_MINUTES = {
    "en": lambda n: f"{n} minute" + ("" if n == 1 else "s"), "de": lambda n: f"{n} Minute" + ("" if n == 1 else "n"),
    "fr": lambda n: f"{n} minute" + ("" if n == 1 else "s"), "es": lambda n: f"{n} minuto" + ("" if n == 1 else "s"),
    "it": lambda n: f"{n} minut" + ("o" if n == 1 else "i"), "pt": lambda n: f"{n} minuto" + ("" if n == 1 else "s"),
    "nl": lambda n: f"{n} minuut" if n == 1 else f"{n} minuten",
    "ru": lambda n: f"{n} " + ("минуту" if n % 10 == 1 and n % 100 != 11 else "минуты" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "минут"),
}


# Localised whole-day phrases (the ownership-transfer lifetime is 7 days). Used only when the lifetime is a whole number of days.
_DAYS = {
    "en": lambda n: f"{n} day" + ("" if n == 1 else "s"), "de": lambda n: f"{n} Tag" + ("" if n == 1 else "e"),
    "fr": lambda n: f"{n} jour" + ("" if n == 1 else "s"), "es": lambda n: f"{n} día" + ("" if n == 1 else "s"),
    "it": lambda n: f"{n} giorn" + ("o" if n == 1 else "i"), "pt": lambda n: f"{n} dia" + ("" if n == 1 else "s"),
    "nl": lambda n: f"{n} dag" if n == 1 else f"{n} dagen",
    "ru": lambda n: f"{n} " + ("день" if n % 10 == 1 and n % 100 != 11 else "дня" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "дней"),
}


def normalise_locale(locale: str | None) -> str:
    return locale if locale in SUPPORTED_LOCALE_CODES else "en"


def _duration(locale: str, seconds: int) -> str:
    if seconds % 86400 == 0 and seconds >= 7 * 86400:      # whole weeks read better as days; the 24 h and 72 h lifetimes keep their hour phrasing
        return _DAYS[locale](seconds // 86400)
    if seconds % 3600 == 0:
        return _HOURS[locale](seconds // 3600)
    return _MINUTES[locale](max(1, seconds // 60))


def render(kind: str, *, locale: str | None, link: str | None = None, expires_in_seconds: int = 0) -> Rendered:
    """Render one transactional message. ``link`` is built by the server from the trusted application origin."""
    if kind not in KINDS:
        raise ValueError("unknown message kind")
    loc = normalise_locale(locale)
    tpl = _T[loc][kind]
    body = tpl["body"].format(link=link or "", expiry=_duration(loc, expires_in_seconds) if expires_in_seconds else "")
    return Rendered(subject=tpl["subject"], body=f"{body}\n\n{BRAND_LINE}", locale=loc)

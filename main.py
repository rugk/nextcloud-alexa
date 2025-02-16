import os
from flask import Flask, send_from_directory
from flask_ask import Ask, question, statement, audio
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from utils.nextcloud_calendar import list_events, create_event
from dateutil.parser import parse
from utils.nextcloud_notes import get_notes_summary, get_single_note, create_note
from utils.nextcloud_tasks import get_task_summary, create_task, finish_task
from utils.imap_email import get_emails_summary, get_single_email
from utils.wake_on_lan import wake_on_lan, sleep_on_lan

# from utils.nextcloud_news import get_news_summary
from utils.nextcloud_music import (
    get_random_playlist,
    get_filtered_playlist,
    get_podcast,
)
from utils.music_queue import MusicQueue
import inspect
from utils.news import get_latest_news

# Patch due to flask ask bug
if not hasattr(inspect, "getargspec"):
    inspect.getargspec = inspect.getfullargspec

app = Flask(__name__)
ask = Ask(app, "/")
load_dotenv()

app.config["ASK_APPLICATION_ID"] = os.getenv("ALEXA_SKILL_ID")

music_queue = MusicQueue()


@ask.launch
def launch():
    speech_text = "Oi, eu sou o pardal, pru pru"
    return (
        question(speech_text)
        .reprompt(speech_text)
        .simple_card("HelloWorld", speech_text)
    )


@ask.intent("AMAZON.HelpIntent")
def help():
    speech_text = "You can say hello to me!"
    return (
        question(speech_text)
        .reprompt(speech_text)
        .simple_card("HelloWorld", speech_text)
    )


@ask.session_ended
def session_ended():
    return "{}", 200


@ask.intent("ListCalendarIntent", default={"event_date": ""})
def list_calendar_intent(event_date=""):
    if not event_date:
        event_date = datetime.now(tz=timezone(timedelta(hours=-3))).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        event_date = parse(event_date).replace(tzinfo=timezone.utc)

    end_date = event_date + timedelta(days=1)

    events = list_events(event_date, end_date)
    speech_text = f"Seus eventos de {str(event_date.date())} são: {events}"

    return statement(speech_text).simple_card("Eventos Calendário", speech_text)


@ask.intent("CreateCalendarIntent", default={"event_query": "Sem descrição"})
def create_calendar_intent(event_query):
    create_event(event_query)
    speech_text = f"Criado evento {event_query}"
    return statement(speech_text).simple_card("Criar Evento", speech_text)


@ask.intent("ListTasksIntent")
def list_tasks_intent():
    speech_text = f"Suas próximas 5 tarefas são: {get_task_summary()}."
    return statement(speech_text).simple_card("Lista de tarefas", speech_text)


@ask.intent("FinishTaskIntent", default={"task_name": "Sem descrição"})
def finish_task_intent(task_name):
    finish_task(task_name)
    speech_text = f"Finalizando tarefa {task_name}"
    return statement(speech_text).simple_card("Finalizar tarefa", speech_text)


@ask.intent("CreateTaskIntent", default={"task_name": "Sem descrição"})
def create_task_intent(task_name):
    create_task(task_name)
    speech_text = f"Criado tarefa {task_name}"
    return statement(speech_text).simple_card("Criar Tarefa", speech_text)


@ask.intent("ListNotesIntent")
def list_notes_intent():
    speech_text = f"Suas primeiras 5 notas são: {get_notes_summary()}. Peça para ler uma nota para detalhes."
    return statement(speech_text).simple_card("Lista de notas", speech_text)


@ask.intent("ReadNoteIntent", default={"note_name": ""})
def read_note_intent(note_name):
    speech_text = get_single_note(note_name)
    return statement(speech_text).simple_card("Nota", speech_text)


@ask.intent("CreateNoteIntent", default={"note_content": "Sem descrição"})
def create_note_intent(note_content):
    create_note(note_content)
    speech_text = "Nota criada!"
    return statement(speech_text).simple_card("Criar Nota", speech_text)


@ask.intent("ListEmailsIntent")
def list_emails_intent():
    speech_text = f"Seus últimos 5 emails são: {get_emails_summary()}. Peça para ler um email para detalhes."
    return statement(speech_text).simple_card("Lista de emails", speech_text)


@ask.intent("ReadEmailIntent", default={"email_subject": ""})
def read_email_intent(email_subject):
    speech_text = get_single_email(email_subject)
    return statement(speech_text).simple_card("Email", speech_text)


@ask.intent("ListNewsIntent")
def list_news_intent():
    speech_text = get_latest_news()
    return statement(speech_text)


@app.route("/music/<path:name>")
def music_folder(name):
    return send_from_directory("music/", name)


@ask.intent("PlayMusicIntent")
def play_random_tracks():
    speech_text = "Tocando músicas"
    playlist = get_random_playlist()
    music_url = music_queue.start_queue(playlist)
    return audio(speech_text).play(music_url)


@ask.intent("SearchMusicIntent", default={"music_query": ""})
def play_filtered_tracks(music_query):
    speech_text = "Tocando músicas"
    playlist = get_filtered_playlist(music_query)
    music_url = music_queue.start_queue(playlist)
    return audio(speech_text).play(music_url)


@ask.on_playback_started()
def playback_started():
    return statement("")


@ask.on_playback_stopped()
def playback_stopped():
    return statement("")


@ask.on_playback_failed()
def playback_failed() -> tuple:
    return statement("")


@ask.on_playback_nearly_finished()
def playback_nearly_finished():
    next_music = music_queue.next_item()
    if next_music:
        return audio().play(next_music)
    else:
        return statement("")


@ask.intent("AMAZON.PauseIntent")
def pause():
    return audio().stop()


@ask.intent("AMAZON.ResumeIntent")
def resume():
    return audio().resume()


@ask.intent("AMAZON.StopIntent")
def stop():
    music_queue.clear()
    return audio("Parando músicas").stop()


@ask.intent("AMAZON.CancelIntent")
def cancel() -> audio:
    music_queue.clear()
    return audio().clear_queue(stop=True)


@ask.intent("AMAZON.NextIntent")
def next_track():
    next_music = music_queue.next_item()

    if next_music:
        return audio().play(next_music)
    else:
        return statement("Todas as músicas foram tocadas")


@ask.intent("AMAZON.PreviousIntent")
def previous_track():
    previous_music = music_queue.previous_item()

    if previous_music:
        return audio().play(previous_music)
    else:
        return statement("Não há música anterior")


@ask.intent("AMAZON.StartOverIntent")
def restart_track():
    current_music = music_queue.current()

    if current_music:
        return audio().play(current_music)
    else:
        return statement("Não há músicas")


@ask.intent("AMAZON.FallbackIntent")
@ask.intent("AMAZON.LoopOffIntent")
@ask.intent("AMAZON.LoopOnIntent")
@ask.intent("AMAZON.RepeatIntent")
@ask.intent("AMAZON.ShuffleOffIntent")
@ask.intent("AMAZON.ShuffleOnIntent")
def unsupported_intent() -> statement:
    return statement("Comando não suportado")


@ask.intent("SearchPodcastIntent", default={"podcast_query": ""})
def play_podcast(podcast_query):
    podcast_name, playlist = get_podcast(podcast_query)
    speech_text = f"Tocando podcast {podcast_name}"
    music_url = music_queue.start_queue(playlist)
    return audio(speech_text).play(music_url)


@ask.default_intent
def default_intent():
    speech_text = "Esta ação não é suportada ainda. Por favor, tente novamente"
    return statement(speech_text)


@ask.intent("DailyDigestIntent")
def daily_digest():
    event_date = datetime.now(tz=timezone(timedelta(hours=-3))).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_date = event_date + timedelta(days=1)

    events = list_events(event_date, end_date)

    speech_text = f"Aqui está seu resumo do dia. Seus eventos de hoje são: {events}. Seus últimos 5 emails são: {get_emails_summary()}. Suas próximas 5 tarefas são: {get_task_summary()}. Suas primeiras 5 notas são: {get_notes_summary()}. Tenha um bom dia!"

    return statement(speech_text)


@ask.intent("WakeOnLanIntent")
def wake_on_lan_intent():
    wake_on_lan()
    speech_text = "Ligando computador"
    return statement(speech_text)


@ask.intent("SleepOnLanIntent")
def sleep_on_lan_intent():
    sleep_on_lan()
    speech_text = "Ligando computador"
    return statement(speech_text)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

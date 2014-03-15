import os
from flask import Flask, abort, request, render_template
import re
from twilio import twiml

from first_results import first_results
from local_settings import *

import pprint

app = Flask(__name__, static_url_path='/static')
 
@app.route('/')
def index():
    data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
    event_data = data.get_event_data(FIRST_EVENT, year='')
    return render_template('index.html', event=event_data)

@app.route('/harvest')
def harvest():
    try:
        data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
        data.fetch_all_data()
        return 'All fetched'
    except:
        abort(500)

@app.route('/voice', methods=['POST'])
def voice():
    r = twiml.Response()
    r.say('Hello.')
    with r.gather(action='/gather', finishOnKey='#', timeout='7', numDigits='4') as g:
        g.say('Enter the team number you want to know about, then press pound.')
    r.pause()
    r.say('Goodbye')
    r.hangup()
    return str(r)

@app.route('/gather', methods=['POST'])
def gather():
    r = twiml.Response()
    message = request.form['Digits']
    data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
    info = data.get_full_team_info(int(message), FIRST_EVENT)

    if info['matches'] == []:
        r.say('It looks like team ' + number_to_speech(message) + ' isn\'t registered for this event ('+FIRST_EVENT+')')

    elif info['next_match']:
        string_data = dict()
        string_data['team_num'] = number_to_speech(message)
        string_data['rank'] = info['ranking']['rank']
        string_data['next_match'] = info['next_match']['number']
        string_data['next_time'] = info['next_match']['time'].strftime('%I:%M %p')

        if int(message) in info['next_match']['red']:
            string_data['next_alliance'] = 'red'
            opp_alliance = 'blue'
        else:
            string_data['next_alliance'] = 'blue'
            opp_alliance = 'red'

        allies = info['next_match'][string_data['next_alliance']]
        allies.remove(int(message))
        opps = info['next_match'][opp_alliance]

        string_data['ally_0'] = number_to_speech(allies[0])
        string_data['ally_1'] = number_to_speech(allies[1])
        string_data['opp_0'] = number_to_speech(opps[0])
        string_data['opp_1'] = number_to_speech(opps[1])
        string_data['opp_2'] = number_to_speech(opps[2])
        string_data['total_teams'] = len(data.get_rankings(FIRST_EVENT, year=''))

        message = "Team {team_num!s} is ranked number {rank!s} out of {total_teams!s} teams. "
        message = message + "They play next in match number {next_match!s} at {next_time!s} on the {next_alliance!s} alliance. "
        message = message + "They will be paired with teams {ally_0!s} and {ally_1!s}. "
        message = message + "The opposing alliance will be made up of teams {opp_0!s} and {opp_1!s} and {opp_2!s}"

        r.say(message.format(**string_data))

    else:
        string_data = dict()
        string_data['total_teams'] = len(data.get_rankings(FIRST_EVENT, year=''))
        string_data['team_num'] = number_to_speech(message)
        string_data['record'] = info['ranking']['record']
        string_data['rank'] = info['ranking']['rank']

        message = "Team {team_num!s} is ranked #{rank!s} out of {total_teams!s}. "
        message = message + "They don't play in any more seeding matches. "
        message = message + "I don't have any data regarding elimination matches."

        r.say(message.format(**string_data))

    r.say('Goodbye')
    r.hangup()
    return str(r)


@app.route('/sms', methods=['POST'])
def sms():
    r = twiml.Response()
    message = request.form['Body'].lower()
    data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
    if re.search('^\d{0,4}$', message):
        info = data.get_full_team_info(int(message), FIRST_EVENT)

        if info['matches'] == []:
            r.sms('It looks like team ' + message + ' isn\'t registered for this event ('+FIRST_EVENT+')')

        elif info['next_match']:
            string_data = dict()
            string_data['team_num'] = message
            string_data['record'] = info['ranking']['record']
            string_data['rank'] = info['ranking']['rank']
            string_data['next_match'] = info['next_match']['number']
            string_data['next_time'] = info['next_match']['time'].strftime('%I:%M %p')

            if int(message) in info['next_match']['red']:
                string_data['next_alliance'] = 'red'
                opp_alliance = 'blue'
            else:
                string_data['next_alliance'] = 'blue'
                opp_alliance = 'red'

            allies = info['next_match'][string_data['next_alliance']]
            allies.remove(int(message))
            opps = info['next_match'][opp_alliance]

            string_data['ally_0'] = allies[0]
            string_data['ally_1'] = allies[1]
            string_data['opp_0'] = opps[0]
            string_data['opp_1'] = opps[1]
            string_data['opp_2'] = opps[2]
            string_data['total_teams'] = len(data.get_rankings(FIRST_EVENT, year=''))

            message = "Team {team_num!s} ({record!s}) is ranked #{rank!s}/{total_teams!s}. "
            message = message + "They play next in match #{next_match!s} ({next_time!s}) on the {next_alliance!s} alliance "
            message = message + "(w/ {ally_0!s}, {ally_1!s}; vs {opp_0!s}, {opp_1!s}, {opp_2!s})."

            r.sms(message.format(**string_data))

        else:
            string_data = dict()
            string_data['total_teams'] = len(data.get_rankings(FIRST_EVENT, year=''))
            string_data['team_num'] = message
            string_data['record'] = info['ranking']['record']
            string_data['rank'] = info['ranking']['rank']

            message = "Team {team_num!s} ({record!s}) is ranked #{rank!s}/{total_teams!s}. "
            message = message + "They don't play in any more seeding matches, and I don't "
            message = message + "have any data on the elimination matches."

            r.sms(message.format(**string_data))

        return str(r)


    elif message == 'harvest':
        try:
            data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
            data.fetch_all_data()
            message = "Data successfully updated."
        except:
            message = "Something went wrong with the harvest."

        r.sms(message)
        return str(r)

    else:
        r.sms('Text a team number for information about that team, including upcoming matches')
        return str(r)
    
def number_to_speech(number):
    resp = ''
    for i in range(0, len(str(number))):
        resp = resp + str(number)[i] + ' '
    return resp

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    if port == 5000:
        app.debug = True
    app.run(host='0.0.0.0', port=port)

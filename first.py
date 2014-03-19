import os
from flask import Flask, abort, request, render_template
import re
from twilio import twiml

from first_results import first_results
from local_settings import *

app = Flask(__name__, static_url_path='/static')
 
@app.route('/')
def index():
    data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
    event_data = data.get_event_data(FIRST_EVENT, year='')
    return render_template('index.html', event=event_data)

@app.route('/<int:team_number>')
def get_team_stats(team_number):
    data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
    info = data.get_full_team_info(team_number, FIRST_EVENT)
    if info['ranking']:
        return render_template('team_stats.html', info=info, team_number=team_number, record=team_record(team_number, info['matches']))
    else:
        return "Data for team " + str(team_number) + " isn't available for this event (" + FIRST_EVENT + ")"

@app.route('/rankings')
def rankings():
    data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
    rankings = data.get_rankings(FIRST_EVENT, year='')
    return render_template('rankings.html', rankings=rankings)

@app.route('/harvest')
def harvest():
    try:
        data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
        data.fetch_all_data(get_events=True)
        return 'All fetched'
    except:
        abort(500)

@app.route('/voice', methods=['POST'])
def voice():
    r = twiml.Response()
    r.say('Hello.')
    with r.gather(action='/process_call', finishOnKey='#', timeout='5') as g:
        g.say('Enter the team number you want to know about, then press pound.')
    r.pause()
    r.say('Goodbye')
    r.hangup()
    return str(r)

@app.route('/process_call', methods=['POST'])
def process_call():
    r = twiml.Response()
    r.pause()
    message = request.form['Digits']
    data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
    info = data.get_full_team_info(int(message), FIRST_EVENT)
    elim_matches = data.count_elimination_matches(FIRST_EVENT)
    string_data = get_words(int(message), info)

    if info['matches'] == []:
        r.say('It looks like team ' + number_to_speech(message) + ' isn\'t registered for this event ('+FIRST_EVENT+')')
    elif info['next_match']:
        message = "Team {team_num_speech!s} is ranked number {rank!s} out of {total_teams!s} teams. "
        message = message + "They play next in match number {next_match!s} at {next_time!s} on the {next_alliance!s} alliance. "
        message = message + "They will be paired with teams {ally_0_speech!s} and {ally_1_speech!s}. "
        message = message + "The opposing alliance will be made up of teams {opp_0_speech!s} and {opp_1_speech!s} and {opp_2_speech!s}. "
        r.say(message.format(**string_data))

    elif elim_matches > 0:
        message = "Team {team_num_speech!s} is ranked {rank!s} out of {total_teams!s}. "
        message = message + "They aren't listed as playing any more matches and elimination matches have been scheduled. "
        message = message + "This usually means that the aren't playing in elimination matches. "
        r.say(message.format(**string_data))

    elif elim_matches == 0:
        message = "Team {team_num_speech!s} is ranked {rank!s} out of {total_teams!s}. "
        message = message + "They aren't listed as playing any more matches, but data isn't yet available for elimination matches. "
        message = message + "Check back later to find out if they're playing again. "
        r.say(message.format(**string_data)) 

    if info['last_match']:
        message = "In their last match, number {match_num!s}, team {team_num_speech!s} {result!s}, {score!s}. "
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
    	elim_matches = data.count_elimination_matches(FIRST_EVENT)
        string_data = get_words(int(message), info)
        if info['matches'] == []:
            r.sms('Either team ' + message + ' isn\'t registered for this event, or FIRST hasn\'t published match data yet. ('+FIRST_EVENT+')')
        elif info['next_match']:
            message = "Team {team_num!s} ({record!s}) is ranked #{rank!s}/{total_teams!s}. "
            message = message + "They play next in match {next_match!s} ({next_time!s}) on the {next_alliance!s} alliance "
            message = message + "(w/ {ally_0!s}, {ally_1!s}; vs {opp_0!s}, {opp_1!s}, {opp_2!s})."
            r.sms(message.format(**string_data))
        elif elim_matches > 0:
            message = "Team {team_num!s} ({record!s}) is ranked #{rank!s}/{total_teams!s}. "
            message = message + "They\'re not on the schedule to play anymore matches. "
            message = message + "Elimination rounds have already been scheduled."
            r.sms(message.format(**string_data))
        elif elim_matches == 0:
            message = "Team {team_num!s} ({record!s}) is ranked #{rank!s}/{total_teams!s}. "
            message = message + "They\'re not on the schedule to play anymore matches. "
            message = message + "Elimination rounds have not been scheduled."
            r.sms(message.format(**string_data))

    elif re.search('^\d{0,4} last$', message):
        num = re.search('^(\d{0,4}) last$', message).group(1)
        info = data.get_full_team_info(int(num), FIRST_EVENT)

        if info['last_match'] == None:
            r.sms('Team ' + num + ' hasn\'t played any matches yet. ('+FIRST_EVENT+')')
        else:
            string_data = get_words(num, info)
            message = "Team {team_num!s}({record!s}) {result!s} match {match_num!s}, {score!s}."
            r.sms(message.format(**string_data))

    elif message == 'harvest':
        try:
            data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
            data.fetch_all_data()
            message = "Data successfully updated."
        except:
            message = "Something went wrong with the harvest."

        r.sms(message)

    else:
        r.sms('Text a team number for information about that team, including upcoming matches. Follow it with \'last\' to see results from the last match.')

    return str(r)

def get_words(team_number, team_data):
        data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
        string_data = dict()

        string_data['team_num'] = team_number
        string_data['team_num_speech'] = number_to_speech(team_number)

        string_data['total_teams'] = len(data.get_rankings(FIRST_EVENT, year=''))

        string_data['record'] = team_record(team_number, team_data['matches'])
        string_data['rank'] = team_data['ranking']['rank']

        if team_data['last_match']:
            string_data['last_num'] = team_data['last_match']['number']
            string_data['match_num'] = team_data['last_match']['number']
            if int(team_number) in team_data['last_match']['red']:
                if team_data['last_match']['red_score'] > team_data['last_match']['blue_score']:
                    string_data['result'] = 'won'
                    string_data['score'] = str(team_data['last_match']['red_score']) + '-' + str(team_data['last_match']['blue_score'])
                elif info['last_match']['red_score'] < info['last_match']['blue_score']:
                    string_data['result'] = 'lost'
                    string_data['score'] = str(team_data['last_match']['blue_score']) + '-' + str(team_data['last_match']['red_score'])
                else:
                    string_data['result'] = 'tied'
                    string_data['score'] = str(team_data['last_match']['blue_score']) + '-' + str(team_data['last_match']['red_score'])
            else:
                if team_data['last_match']['red_score'] < team_data['last_match']['blue_score']:
                    string_data['result'] = 'won'
                    string_data['score'] = str(team_data['last_match']['red_score']) + '-' + str(team_data['last_match']['blue_score'])
                elif info['last_match']['red_score'] > team_data['last_match']['blue_score']:
                    string_data['result'] = 'lost'
                    string_data['score'] = str(team_data['last_match']['blue_score']) + '-' + str(team_data['last_match']['red_score'])
                else:
                    string_data['result'] = 'tied'
                    string_data['score'] = str(team_data['last_match']['blue_score']) + '-' + str(team_data['last_match']['red_score'])

        if team_data['next_match']:
            string_data['next_match'] = team_data['next_match']['number']
            string_data['next_time'] = team_data['next_match']['time'].strftime('%I:%M %p')

            if int(team_number) in team_data['next_match']['red']:
                string_data['next_alliance'] = 'red'
                opp_alliance = 'blue'
            else:
                string_data['next_alliance'] = 'blue'
                opp_alliance = 'red'

            allies = team_data['next_match'][string_data['next_alliance']]
            allies.remove(int(team_number))
            opps = team_data['next_match'][opp_alliance]

            string_data['ally_0'] = allies[0]
            string_data['ally_1'] = allies[1]
            string_data['opp_0'] = opps[0]
            string_data['opp_1'] = opps[1]
            string_data['opp_2'] = opps[2]
        
            string_data['ally_0_speech'] = number_to_speech(allies[0])
            string_data['ally_1_speech'] = number_to_speech(allies[1])
            string_data['opp_0_speech'] = number_to_speech(opps[0])
            string_data['opp_1_speech'] = number_to_speech(opps[1])
            string_data['opp_2_speech'] = number_to_speech(opps[2])

        return string_data

def team_record(team_number, matches, return_string=True):
    record = dict()
    record['wins'] = 0
    record['losses'] = 0
    record['ties'] = 0
    for match in matches:
        if int(team_number) in match['red']:
            if int(match['red_score']) > int(match['blue_score']):
                record['wins'] += 1
            elif int(match['red_score']) < int(match['blue_score']):
                record['losses'] += 1
            elif int(match['red_score'] != -1):
                record['ties'] += 1
        else:
            if int(match['red_score']) < int(match['blue_score']):
                record['wins'] += 1
            elif int(match['red_score']) > int(match['blue_score']):
                record['losses'] += 1
            elif int(match['red_score'] != -1):
                record['ties'] += 1

    if return_string:
        return str(record['wins']) + '-' + str(record['losses']) + '-' + str(record['ties'])
    else:
        return record
            
    
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

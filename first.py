import os
from flask import Flask, abort, request
import re
from twilio import twiml

from first_results import first_results
from local_settings import *

app = Flask(__name__, static_url_path='/static')
 
@app.route('/')
def index():
    return 'Hello World.'

@app.route('/harvest')
def harvest():
    try:
        data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
        data.fetch_all_data()
        return 'All fetched'
    except:
        abort(500)

@app.route('/sms', methods=['POST'])
def sms():
    r = twiml.Response()
    message = request.form['Body'].lower()

    data = first_results(uri=MONGO_URI, collection=MONGO_COLL)
    if re.search('^\d{0,4}$', message):
        info = data.get_full_team_info(int(message), FIRST_EVENT)
        if info['matches'] == []:
            r.sms('It looks like team ' + message + ' isn\'t registered for this event ('+FIRST_EVENT+')')
            return str(r)        

        if info['next_match']:
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
            return str(r)

        else:
            string_data = dict()
            string_data['total_teams'] = len(data.get_rankings(FIRST_EVENT, year=''))
            string_data['team_num'] = message
            string_data['record'] = info['ranking']['record']
            string_data['rank'] = info['ranking']['rank']

            message = "Team {team_num!s} ({record!s}) is ranked #{rank!s}/{total_team!s}. "
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
    
    

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    if port == 5000:
        app.debug = True
    app.run(host='0.0.0.0', port=port)

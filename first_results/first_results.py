from bs4 import BeautifulSoup
import requests
from datetime import datetime, timedelta
import re
import pymongo

class first_results:

    def __init__(self, uri, collection):
        client = pymongo.MongoClient(uri)
        self.db = client[collection]

    def get_rankings(self, event, year=2014, from_web=False):
        db_rankings = self.db.rankings

        if from_web:
            teams = []
            rankings_url = 'http://www2.usfirst.org/' + str(year) + 'comp/events/' + event + '/rankings.html'
            try:
                page = requests.get(rankings_url)
                page.raise_for_status()
            except requests.exceptions.HTTPError:
                return None
        
            soup = BeautifulSoup(page.content)

            tables = soup.findAll('table')

            rankings_table = tables[2]
            for tr in rankings_table.findAll('tr')[1:]:
                team = dict()
                tds = tr.findAll('td')
                if tds[0].string != None:
                    team['event'] = str(year) + event
                    team['rank'] = int(tds[0].string)
                    team['team'] = int(tds[1].string)
                    team['qs'] = float(tds[2].string)
                    team['assist'] = float(tds[3].string)
                    team['auto'] = float(tds[4].string)
                    team['tc'] = float(tds[5].string)
                    team['teleop'] = float(tds[6].string)
                    team['record'] = tds[7].string
                    team['dq'] = int(tds[8].string)
                    team['played'] = int(tds[9].string)
                    team['_id'] = str(year) + '-' + event + '-' + str(team['team'])
                    teams.append(team)
                    db_rankings.update({'_id': team['_id']}, team, upsert=True)
            return teams
        else:
            return list(db_rankings.find({'event': str(year) + event}).sort('rank', 1))

    def get_results(self, event, year=2014, from_web=False):
        matches = []
        matches = self.db.matches
        if from_web:
            qual_url = 'http://www2.usfirst.org/' + str(year) + 'comp/events/' + event + '/matchresults.html'
            try:
                page = requests.get(qual_url)
                page.raise_for_status()
            except requests.exceptions.HTTPError:
                return None

            soup = BeautifulSoup(page.content)

            tables = soup.findAll('table')

            date_range = tables[1].findAll('tr')[0].findAll('td')[1].findAll('p')[0].string

            start_date = datetime.strptime(date_range.split('-', 1)[0].strip(), '%m/%d/%Y')
            end_date = datetime.strptime(date_range.split('-', 1)[1].strip(), '%m/%d/%Y')

            if end_date - start_date == timedelta(days=2):
                current_date = start_date + timedelta(days=1)
            else:
                current_date = start_date

            results_table = tables[2]

            meridian = None

            match_list = []
            for tr in results_table.findAll('tr')[2:]:
                match = dict()
                tds = tr.findAll('td')
                if tds[0].string != None:
                    match['time'] = datetime.strptime(tds[0].string + ' ' + current_date.strftime('%d/%m/%Y'), '%I:%M %p %d/%m/%Y')
                    if match['time'].strftime('%p') == 'AM' and  meridian == 'PM':
                        current_date = current_date + timedelta(days=1)
                        match['time'] = datetime.strptime(tds[0].string + ' ' + current_date.strftime('%d/%m/%Y'), '%I:%M %p %d/%m/%Y')
                    meridian = match['time'].strftime('%p')
                    match['event'] = match['time'].strftime('%Y') + event

                    match['number'] = int(tds[1].string)
                    match['red'] = [int(tds[2].string), int(tds[3].string), int(tds[4].string)]
                    match['blue'] = [int(tds[5].string), int(tds[6].string), int(tds[7].string)]
                    match['red_score'] = int(tds[8].string) if tds[8].string != None else -1
                    match['blue_score'] = int(tds[9].string) if tds[9].string != None else -1
                    match['match_type'] = 'Q'
                    match['_id'] = str(year) + '-' + event + '-' + str(match['number'])
                    matches.update({'_id': match['_id']}, match, upsert=True)
                    match_list.append(match)

            meridian = None

            if len(tables) > 3:
                for tr in tables[3].findAll('tr')[3:]:
                    match = dict()
                    tds = tr.findAll('td')
                    if tds[3].string != None:
                        match['time'] = datetime.strptime(tds[0].string + ' ' + current_date.strftime('%d/%m/%Y'), '%I:%M %p %d/%m/%Y')
                        if match['time'].strftime('%p') == 'AM' and  meridian == 'PM':
                            current_date = current_date + timedelta(days=1)
                            match['time'] = datetime.strptime(tds[0].string + ' ' + current_date.strftime('%d/%m/%Y'), '%I:%M %p %d/%m/%Y')
                        meridian = match['time'].strftime('%p')
                        match['event'] = match['time'].strftime('%Y') + event
                        match['number'] = tds[1].string
                        match['red'] = [int(tds[3].string), int(tds[4].string), int(tds[5].string)]
                        match['blue'] = [int(tds[6].string), int(tds[7].string), int(tds[8].string)]
                        match['red_score'] = int(tds[9].string) if tds[9].string != None else -1
                        match['blue_score'] = int(tds[10].string) if tds[10].string != None else -1
                        match['match_type'] = 'E'
                        match['_id'] = str(year) + '-' + event + '-' + str(match['number'])
                        matches.update({'_id': match['_id']}, match, upsert=True)
                        match_list.append(match)

            return match_list
        else:
            return list(matches.find({'event': int(year) + event}))

    def get_event_data(self, event, year=2014, from_web=False):
        events = self.db.events

        if from_web:
            url = 'http://www.thebluealliance.com/api/v2/event/' + str(year) + event
            event_info = requests.get(url, headers={'X-TBA-App-Id': 'frc1137:database_populator:0.0.1'})
            event_info = event_info.json()

            teams = []
            registrant_url = 'http://www.thebluealliance.com/api/v2/event/' + str(year) + event + '/teams'
            event_teams = requests.get(registrant_url, headers={'X-TBA-App-Id': 'frc1137:database_populator:0.0.1'})
            event_teams = event_teams.json()
            
            for event_team in event_teams:
                teams.append(event_team['team_number'])

            date_format = '%Y-%m-%dT%H:%M:%S'
            event = dict()
            event['code'] = ''.join(event_info['event_code'])
            event['location'] = event_info['location']
            event['name'] = event_info['name']
            event['_id'] = event_info['key']
            event['type'] = event_info['event_type_string']
            event['start'] = datetime.strptime(event_info['start_date'], date_format) + timedelta(hours=-24)
            event['end'] = datetime.strptime(event_info['end_date'], date_format) + timedelta(hours=23, minutes=59)
            event['teams'] = teams
            events.update({'_id': event['_id']}, event, upsert=True)
            return event
        else:
            return events.find_one({'_id': str(year)+event})
      
    def get_events(self, year=None, from_web=False, active=True):
        if from_web:
            # Get event codes from The Blue Alliance website
            url = 'http://www.thebluealliance.com/api/v2/events/2014'
            matches = requests.get(url, headers={'X-TBA-App-Id': 'frc1137:database_populator:0.0.1'})

            # Separate event codes from years
            event_codes = []
            for match in matches.json():
                m = re.search('(\d{4})(.*)$', match)
                event_codes.append(m.group(2))
        elif active:
            events = self.db.events
            right_now = datetime.now()
            event_list = list(events.find({'start': { '$lte': right_now }, 'end': { '$gte': right_now} }))
            event_codes = []
            for event in event_list:
                event_codes.append(event['code'])
        else:
            events = self.db.events
            event_list = list(events.find())
            event_codes = []
            for event in event_list:
                event_codes.append(event['code'])

        return event_codes

    def fetch_all_data(self, get_events=False, year=2014):
    	if get_events:
	    event_codes = self.get_events(year=year, from_web=True)
        else:
            event_codes = self.get_events(year=year, active=True)

        for event in event_codes:
            self.get_event_data(event, year=year, from_web=True)
            self.get_rankings(event, year=year, from_web=True)
            self.get_results(event, year=year, from_web=True)

    def get_team_ranking(self, team, event):
        return self.db.rankings.find_one({'$and': [ {'team': team}, {'event': event}] })

    def get_team_matches(self, team, event):
        return list(self.db.matches.find({'$and': [ { '$or': [ { 'red': {'$in': [team]} },{ 'blue': { '$in': [team]} } ] }, {'event': event}] }).sort('time', 1))

    def get_next_team_match(self, team, event):
        unplayed_matches = list(self.db.matches.find({'$and': [ { '$or': [ { 'red': {'$in': [team]} },{ 'blue': { '$in': [team]} } ] }, {'event': event}, {'red_score': -1}] }).sort('time', 1))
        if len(unplayed_matches) == 0:
            return None
        else:
            return unplayed_matches[0]

    def count_elimination_matches(self, event):
        elimination_matches = list(self.db.matches.find({'$and': [ {'event': event}, {'match_type': 'E'} ] }))
        return len(elimination_matches)

    def get_last_team_match(self, team, event):
        played_matches = list(self.db.matches.find({'$and': [ { '$or': [ { 'red': {'$in': [team]} },{ 'blue': { '$in': [team]} } ] }, {'event': event}, {'red_score': {'$gt': -1}}] }).sort('time', -1))
        if len(played_matches) == 0:
            return None
        else:
            return played_matches[0]

    def get_current_events(self):
        events = self.db.events
        right_now = datetime.now()
        match = list(events.find({'start': { '$lte': right_now }, 'end': { '$gte': right_now} }))
        return match

    def find_current_team_event(self, team):
        events = self.db.events
        right_now = datetime.now()
        match = events.find_one({'start': { '$lte': right_now }, 'end': { '$gte': right_now}, 'teams': {'$in': [team]} })
        return match

    def get_full_team_info(self, team, event=None):
        if event == None:
            event = self.find_current_team_event(team)

        info = dict()
        if event == None:
            info['event'] = event
            info['ranking'] = None
            info['matches'] = []
            info['next_match'] = None
            info['last_match'] = None
        else:
            info['event'] = event
            info['ranking'] = self.get_team_ranking(team, event['_id'])
            info['matches'] = self.get_team_matches(team, event['_id'])
            info['next_match'] = self.get_next_team_match(team, event['_id'])
            info['last_match'] = self.get_last_team_match(team, event['_id'])
        return info


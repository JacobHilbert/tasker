import math
import os
from datetime import datetime

import pyon
from slugify import slugify
import dateparser


class posix:
	def string(f:float):
		return "inf" if f == float("inf") else "nan" if math.isnan(f) else str(datetime.fromtimestamp(f))
	def timestamp(s:str):
		return float("inf") if s=="inf" else float("nan") if s=="nan" else dateparser.parse(s,settings={'DATE_ORDER': 'YMD'}).timestamp()

class Task:
	# Class stuff
	title_dict = dict()
	slug_dict  = dict()
	normal_args   = ["title","status","goal"]
	seconds_args  = ["period"]
	stringed_args = ["start","end"]
	no_state_args = ["notes","history"]
	
	def from_file(filename):
		data = pyon.load(filename)
		data["period"] = data["period"]*24*60*60
		data["start"] = posix.timestamp(data["start"])
		data["end"] = posix.timestamp(data["end"])
		return Task(**data)
	def from_dict(data:dict):
		data["period"] = data["period"]*24*60*60
		data["start"] = posix.timestamp(data["start"])
		data["end"] = posix.timestamp(data["end"])
		return Task(**data)
	
	# Instance stuff
	def __init__(self,title,status=float("nan"),goal=1,period=float("inf"),start=None,end=float("inf"),notes={},history=None):
		'''Task internal class. All init arguments (except title) must be given in seconds, 
		which for dates mean posix timestamp.
		
		kwargs:
			title   : str
			status  : float
			goal    : float
			period  : number of seconds
			start   : float timestamp
			end     : float timestamp
			notes   : dict(number->note)
			history : [["datestr",float,str]]
		'''
		# consistency checks
		if start is None:
			start = datetime.now().timestamp()
		if history is None:
			history = []
		if math.isnan(end):
			raise ValueError("`end` cannot be nan.\n" "For undefined end time use float('inf').\n")
		if end < start:
			raise ValueError(f"`end` ({posix.string(end)}) cannot be sooner than `start` ({posix.string(start)})")
		if period < 1:
			raise ValueError(f"`period` cannot be less than a second")
		# usual stuff
		self.title   = title
		self.slug    = slugify(title)
		self.status  = status
		self.goal    = goal
		self.start   = start
		self.end     = end
		self.period  = period
		self.history = history
		self.notes   = notes
		# register
		Task.slug_dict[self.slug]   = self
		Task.title_dict[self.title] = self
		self.report("loaded")
		self.update()
	
	def __repr__(self):
		return f"Task(title='{self.title}',...)"
	def __lt__(self,other):
		return self.end < other.end
	def __eq__(self,other):
		return self.end == other.end
	
	def report(self,who,message=''):
		self.history.append([
			posix.string(datetime.now().timestamp()),
			self.status,
			who+": "*bool(message)+message
		])
	def update(self):
		initial = str(self.data_dict())
		# go to zero state if state is nan (unstarted) and task already started
		if math.isnan(self.status) and datetime.now().timestamp() > self.start:
			self.status = 0.0
			self.report("started")
		# completed? Only ask if finite.
		if math.isfinite(self.status) and self.status >= self.goal:
			self.status = float('inf')
			self.report("completed")
		# a period has passed?
		if (diff:=datetime.now().timestamp() - self.start) > self.period:
			self.start += (diff//self.period)*self.period
			self.end = self.start + self.period
			self.status = 0.0
			self.report("restarted")
		final = str(self.data_dict())
		# recurse until nothing changes
		if final != initial: # An infinite loop could only happens when the period is smaller that the running time 
			self.update() # of one function iteration. Since period must be longer than a second, this is safe
	def progress(self,amount=1,up_to=False):
		'''Add `amount` to task status.
		If `up_to` is se to True, status will be set to `amount`
		Every change of state will be reported to history'''
		self.update() # mus be before and after
		if up_to:
			self.status = amount
		else:
			self.status += amount
		self.report("progress")
		self.update()
	def data_dict(self):
		"The string representation of this dict is meant to represent the acual state of the task"
		normal = {att:getattr(self,att) for att in Task.normal_args}
		seconds = {att:getattr(self,att)/(24*60*60) for att in Task.seconds_args}
		stringed = {att:posix.string(getattr(self,att)) for att in Task.stringed_args}
		return {**normal,**seconds,**stringed}
	def save(self,parent_directory=""):
		data = self.data_dict()
		data.update({att:getattr(self,att) for att in Task.no_state_args})
		pyon.dump(data,parent_directory+"/"+self.slug+".pyon")
		print(f"Saved task '{self.title}' on file {self.slug}.pyon")
	def HTML_string(self):
		# this is good
		percentage = 100 if self.status==float("inf") else \
			0 if self.status==float("nan") else \
			round(self.status/self.goal*100)
		# this is good
		delta_days = (self.end-datetime.now().timestamp())/(60*60*24)
		# this is great
		kind = "progress-bar-danger" if delta_days<=1.5 else \
			"progress-bar-warning" if delta_days<=3 else \
			"progress-bar-info" if delta_days<=4 else \
			"progress-bar-success" if math.isinf(self.status) else ""
		color = {
			"" : "gray",#"#337ab7" ,
			"progress-bar-success" : "#5cb85c",
			"progress-bar-info" : "#5bc0de",
			"progress-bar-warning" : "#f0ad4e",
			"progress-bar-danger" : "#d9534f"
		}[kind]
		# this is good
		str_deadline = "never" if math.isinf(self.end) else \
			posix.string(self.end)[:-9]
		str_status = str(self.goal) if math.isinf(self.status) else \
			"nan" if math.isnan(self.status) else \
			str(int(self.status))
		# this is... not so good
		note = self.notes.get(self.status+1,"")
		next_str = "Next is item #"+str(int(self.status)+1)+": "*bool(note)+note+"<br><br>" if math.isfinite(self.status) else "<br>"
		# this is great
		return f'''
		<div class="task-box" style="border:4px solid {color};">
			<h3>{self.title}</h3> 
			deadline: {str_deadline} <br>
			{str_status} of {self.goal} completed <br>{next_str}
			<div class="progress">
				<div class="progress-bar {kind}" role="progressbar" style="width:{str(percentage)}%">
					{str(percentage)}%
				</div>
			</div>
		</div>
		'''

# High level functions

def import_all(path="./tasks"):
	paths = [p for p in os.listdir(path) if p.endswith(".pyon")]
	for p in paths:
		Task.from_file(p)

def save_all_tasks(path="./tasks"):
	for task in Task.title_dict.values():
		task.save(path)
	
def HTML_string():
	'''
	<!DOCTYPE html>
	<html>
	<style>
	
	div.task-box {
		text-align: center;
		padding: 10px;
	}
	
	</style>
	<body>
	''' +"\n\n".join(map(lambda s:s.HTML_string(),sorted(Task.title_dict.values())))+'''
	</body>
	</html>
	'''
	

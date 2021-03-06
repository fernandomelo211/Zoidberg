#!/usr/bin/env python

from utilities import uniq, oxfordComma, ownerize
from itertools import permutations, combinations

ANSWER_SUBORDINATE = {
	"time_starting": "at the start",
	"time_ending": "at the end"
}

def is_number(s):
	try:
		float(s)
		return True
	except ValueError:
		return False

class SentenceParser(object):
	def __init__(self, sentence, problem, text):
		# Descriptive units are those which do not get parsed even if they
		# contain spaces. These are things like "pieces of chocolate" as
		# opposed to "blue christmas ornaments"
		self.subordinate_lookup = {}
		self.is_exchange = False
		self.unit_idx = {}
		self.index = 0
		self.is_about_requirements = False
		self.framing_question = False
		self.did_frame_question = False
		self.acting = False
		self.last_variable = None
		self.last_variable_type = None
		self.last_determiner = None
		self.last_operator = None
		self.last_operator_type = None
		self.last_word = None
		self.last_adjective = None
		self.last_tag = None
		self.last_unit = None
		self.last_unit_tag = None
		self.last_unit_index = None
		self.last_adj_index = None
		self.new_units_as_context = False
		self.last_verb_tag = None
		self.last_verb = -1
		self.last_noun_tag = None
		self.last_subtype = None
		self.last_conjunction = None
		self.last_conjunction_tag = None
		self.conjunction_parts = []
		self.phrasing_question = False
		self.subtype = None
		self.is_relative_quantity = False
		self.partial_context = None
		self.last_partial_context = None
		self.partial_subtype = None
		self.comparator_context = None
		self.main_context = None
		self.last_context = None
		self.sentence = sentence
		self.problem = problem
		self.sentence_text = text
		self.is_question = False
		self.question = False
		self.verb_question = False
		self.longest_phrase = None

		# Track any units/adjectives used to refine units to attempt to relate
		# similar context group owners with their relevant chunks of subordinate
		# contexts.
		self.used_unit_adjectives = []

		# The parsed sentence of chunked components
		self.parsed = []

		# Collection of verbs which describe data manipulations
		self.operator = {}
		self.operators = []
		self.raw_operators = []

		# Contexts are the way to define the "Joe" of "Joe's apples"
		self.contexts = []

		# Units are the way to define the "apple" of "Joe's apples"
		self.units = []

		# Actions are like a joint structure of contexts and units
		# in that a context can "own" an action the same way it can
		# own a unit. The action also acts as a "subcontext" as the
		# context owner (in this case, actor) can be "performing" an
		# action which differentiates it from the larger context.
		self.actions = []

		# Subordinate conjunctions; time/place/cause and effect which can
		# identify the time period
		self.conjunctions = []
		self.subordinates = []
		self.subordinate_strings = {}
		self.subordinate_subtypes = {}
		self.word_subtypes = {}

		self.execute()

	def fix_unit(self, u):
		if self.last_adjective is not None and not self.verb_question:
			might_be = None
			might_be_prob = False
			for un in self.problem.units:
				if self.last_adjective in un:
					might_be = un
					might_be_prob = True
					break
			for un in self.units:
				if self.last_adjective in un:
					might_be = un
					might_be_prob = False
					break
			if might_be is not None:
				self.used_unit_adjectives.remove(self.last_adjective)
				subtype = None
				subtype = self.problem.unit_subtypes[might_be]
				self.track(might_be, "unit", subtype, self.last_adj_index)
				self.units.append(might_be)

				self.last_adj_index = -1
				self.last_adjective = None
				return (u, len(self.parsed))
			u = " ".join([self.last_adjective, u])
			o = (u, self.last_adj_index)
			self.last_adj_index = -1
			self.last_adjective = None
			return o
		else:
			return (u, len(self.parsed))

	def track_longer(self, v):
		l = len(v)
		if self.longest_phrase is None or self.longest_phrase < l:
			self.longest_phrase = l

	def track(self, val, attr, subtype=None, index=None, conv=False):
		if val == "even number":
			raise Exception
		if subtype:
			self.word_subtypes[val] = subtype

		if attr == "subordinate":
			self.subordinate_subtypes[val[0]] = subtype

		if attr == "context":
			if subtype is not None:
				self.resolve_context(subtype, val)
			else:
				self.problem.last_contexts["last"] = (val, subtype)

		if attr == "comparator_context":
			if subtype is not None:
				conval = self.resolve_context(subtype, None, True)
				if conv and conval:
					val = conval
				else:
					# Set the subtype for PRP comparator contexts
					val = (val, subtype)

		tup = (val, attr, subtype)
		if index is None or index == len(self.parsed):
			index = len(self.parsed)
			self.parsed.append(tup)
		else:
			self.parsed[index] = tup
		self.track_longer(val)
		self.track_longer(attr)
		return index

	def resolve_context(self, subtype, val=None, compx=False, failTest=False):
		p = self.problem
		plurality, gender = subtype
		is_self = (plurality == "self" or gender == "self")

		if val is not None:
			c_str = ""

			if not isinstance(val, basestring):
				c_str = oxfordComma(val)
			else:
				c_str = val

			data = (val, subtype)
			if not self.is_exchange:
				if not is_self:
					p.previous_contexts["last"] = p.last_contexts["last"]
					p.previous_contexts["plurality"][plurality] = \
						p.last_contexts["plurality"][plurality]
					p.previous_contexts["gender"][gender] = \
						p.last_contexts["gender"][gender]

					p.last_contexts["last"] = data
					p.last_contexts["plurality"][plurality] = data
					p.last_contexts["gender"][gender] = data

				p.all_contexts["plurality"][plurality][c_str] = data
				p.all_contexts["gender"][gender][c_str] = data
			else:
				p.all_targets["plurality"][plurality][c_str] = data
				p.all_targets["gender"][gender][c_str] = data
			return c_str
		else:
			pl_co, ge_co = None, None
			if compx:
				pl_co = p.previous_contexts["plurality"]
				ge_co = p.previous_contexts["gender"]
			else:
				pl_co = p.last_contexts["plurality"]
				ge_co = p.last_contexts["gender"]

			plurality_c = pl_co[plurality]
			gender_c = ge_co[gender]

			be_adaptive = False
			if plurality == "plural" and plurality_c is None and self.is_exchange:
				be_adaptive = True
			elif plurality_c is not None and gender_c is not None:
				if (plurality_c[0] == gender_c[0] or
					gender == "mixed" and plurality == "plural" or
					plurality == "plural"):
					return plurality_c
				else:
					return gender_c
			elif plurality_c is not None:
				return plurality_c
			elif gender_c is not None:
				return gender_c
			elif failTest:
				return None
			else:
				be_adaptive = True

			if be_adaptive:
				# NO matching context could be found; try an adapative context?
				if plurality == "plural":
					adaptive_context = []
					if gender == "mixed":
						adaptive_context.append("masculine")
						adaptive_context.append("feminine")
						adaptive_context.append("neutral")
					elif gender == "masculine":
						adaptive_context.append("masculine")
					elif gender == "feminine":
						adaptive_context.append("feminine")
					elif gender == "neutral":
						adaptive_context.append("neutral")

					context = []
					if not self.is_exchange:
						for cgroup in adaptive_context:
							for pers, deets in p.all_contexts["gender"][cgroup].iteritems():
								context.append(deets)
					else:
						for cgroup in adaptive_context:
							for pers, deets in p.all_targets["gender"][cgroup].iteritems():
								context.append(deets)

					if len(context) == 0:
						return None

					c_str = ""

					if not isinstance(context, basestring):
						c_str = oxfordComma(context)
					else:
						c_str = context

					p.adaptive_context[c_str] = context
					p.adaptive_context[c_str] = context

					return (c_str, self.subtype)
		return None

	def __iter__(self):
			return iter(self.parsed)

	def get_subtype(self, word, tag):
		brain = self.problem.brain
		text = self.sentence_text

		if tag[:2] in ["NN", "WP"] or tag[:3] == "PRP": # Nouns and Pronouns
			return brain.noun_like(word, tag, text)
		else:
			return None

	def execute(self):
		p = self.problem

		def process(word, tag):
			did_something = False
			self.subtype = None
			if self.index == 0 and tag not in ["NNP", "NNPS"]:
				# Fix capitalization for non proper nouns
				word = word.lower()

			word, tag = p.brain.retag(word, tag)
			if tag == "!!!":
				print "Missing retag converter in the brain"
				exit(1)

			if tag in ["NNP", "NNPS"]:
				word = word.capitalize()

			if self.last_conjunction is not None:
				self.conjunction_parts.append(word)

			# Fix the parser as we go on brain retags
			def do_track(subtype, tag):
				if subtype[0] is None and subtype[1] is None:
					subtype = None
					tag = p.brain.retag(word, tag)
					process(word, tag)
					return (False, subtype, tag)
				return (True, subtype, tag)

			if tag in ["NN", "NNS"]:
				if self.last_tag in ["PRP$"]:
					# Detects Jane's friends; probably context
					context = " ".join([self.partial_context, word])
					self.parsed.pop()
					self.last_context = context
					self.contexts.append(context)
					did_something = True
					self.subtype = self.get_subtype(word, tag)

					self.partial_context = None
					self.last_partial_context = None
					self.partial_subtype = None

					track, self.subtype, tag = do_track(self.subtype, tag)

					if track:
						if self.problem.involves_acting:
							conjunction = ((word, tag), self.last_conjunction)
							self.subordinate_strings[word] = " ".join(self.conjunction_parts)
							self.conjunction_parts = []
							self.conjunctions.append(conjunction)
							did_something = True
							self.track(conjunction[0], "subordinate", self.subtype)
						else:
							if self.subtype[0] == "plural" and self.subtype[1] == "mixed":
								# PRP$ will always have a noun like last_subtype
								last_plural, last_gender = self.last_subtype
								# Last Plural Context
								lpc = p.last_contexts["plurality"][last_plural]
								# Last Gender Context
								lgc = p.last_contexts["gender"][last_gender]

								self.last_context = None
								if lgc == lpc:
									self.last_context = lgc
								elif lgc is not None:
									self.last_context = lgc
								elif lpc is not None:
									self.last_context = lpc

								if self.last_context is not None:
									# Last context string
									inc = p.brain.inclusive(word,
										"'{0}' ({1}) in '{2}'".format(self.last_word,
																self.last_context[0],
																context))
									# Add the context by the word for easier lookup
									# this will capture 'her friends' and define
									# the concept of inclusiveness for friends then
									# later auto-apply this to the concept of say,
									# 'his friends'
									p.brain.add("inclusive", context, inc)
							# Assume the first context after a comparison is the
							# comparator context
							if self.is_relative_quantity and not self.comparator_context and self.main_context:
								self.comparator_context = context
								self.track(context, "comparator_context", self.subtype, conv=True)
							else:
								self.main_context = context
								self.track(context, "context", self.subtype)
							p.context_subtypes[context] = self.subtype
				else:
					do_reg_unit = True
					if self.last_conjunction is not None:
						do_reg_unit = False
						do_conj_track = False
						if tag == "NN" and self.last_tag in ["IN"]:
							self.subtype = self.get_subtype(word, tag)
							track, self.subtype, tag = do_track(self.subtype, tag)
							did_something = True
							if track:
								unit = " ".join([self.last_unit, self.last_word, word])
								#rint unit, "a"
								self.problem.descriptive_units.append(unit)
								self.problem.refined_units[self.last_unit] = unit
								self.units.pop()
								del p.unit_subtypes[self.last_unit]
								self.parsed.pop()
								self.parsed.pop()
								self.last_unit = unit
								self.last_unit_tag = tag
								self.last_unit_index = len(self.parsed)
								unit, uidx = self.fix_unit(unit)
								self.units.append(unit)
								p.unit_subtypes[unit] = self.subtype
								self.unit_idx[unit] = self.last_unit_index
								if self.new_units_as_context:
									p.units_acting_as_context[unit] = True
								self.track(unit, "unit", self.subtype, uidx)
						elif tag in ["NN", "NNS"] and self.last_conjunction_tag in ["IN"]:
							self.subtype = self.get_subtype(word, tag)
							track, self.subtype, tag = do_track(self.subtype, tag)
							did_something = True
							if track:
								if self.last_variable is not None:
									unit = word
									self.problem.descriptive_units.append(unit)
									self.problem.refined_units[self.last_unit] = unit
									self.last_unit = unit
									self.last_unit_tag = tag
									self.last_unit_index = len(self.parsed)
									unit, uidx = self.fix_unit(unit)
									self.units.append(unit)
									p.unit_subtypes[unit] = self.subtype
									self.unit_idx[unit] = self.last_unit_index
									if self.new_units_as_context:
										p.units_acting_as_context[unit] = True
									c_unit = " ".join([word, "owned by", p.previous_contexts["last"][0]])
									self.track((c_unit, word, p.previous_contexts["last"][0], p.last_contexts["last"][0]), "context_unit", self.subtype, uidx)
								else:
									do_conj_track = True
						else:
							do_conj_track = True

						do_unset_conj = True
						if do_conj_track:
							unit = word
							do_std = True
							if tag in ["NN", "NNS"]:
								if self.last_tag in ["NN", "NNS"]:
									if self.last_unit is None and self.last_context is not None:
										self.last_context = None
										lc = self.contexts.pop()
										unit = " ".join([lc, word])
									else:
										unit = " ".join([self.last_unit, word])
										self.units.pop()
									self.used_unit_adjectives.append(self.last_word)
									self.parsed.pop()
								ptest = self.parsed.pop()
								self.parsed.append(ptest)
								if ptest[1] == "constant" and self.last_tag != "DT" and self.problem.exestential:
									unit, uidx = self.fix_unit(unit)
									self.last_unit = unit
									self.last_unit_tag = tag
									self.last_unit_index = len(self.parsed)
									self.units.append(unit)
									p.unit_subtypes[unit] = self.subtype
									self.unit_idx[unit] = self.last_unit_index
									#rint unit, "b"
									if self.new_units_as_context:
										p.units_acting_as_context[unit] = True
									self.track(unit, "unit", self.subtype, uidx)
									do_unset_conj = False
									do_reg_unit = False
									do_std = False

							if do_std:
								if word in self.used_unit_adjectives:
									do_unset_conj = False
									do_reg_unit = True
								else:
									conjunction = ((unit, tag), self.last_conjunction)
									self.subordinate_strings[unit] = " ".join(self.conjunction_parts)
									self.conjunction_parts = []
									self.conjunctions.append(conjunction)
									did_something = True
									self.track(conjunction[0], "subordinate", self.subtype)

						if do_unset_conj:
							self.last_conjunction = None

					if do_reg_unit:
						self.subtype = self.get_subtype(word, tag)
						track, self.subtype, tag = do_track(self.subtype, tag)
						did_something = True
						if track:
							#rint "here for", word, tag, self.last_tag, self.last_unit, self.last_word
							unit = word
							do_std_unit = True
							if tag in ["NN", "NNS"] and self.last_tag in ["NN", "NNS"]:
								# rint self.last_word, self.last_tag
								# rint word, tag
								# rint self.parsed
								# rint "----"

								ptest = self.parsed.pop()
								if ptest[1] == "subordinate" and self.last_unit is None:
									cst = self.conjunctions.pop()
									subostr = " ".join([self.subordinate_strings[ptest[0][0]], word])
									del self.subordinate_strings[ptest[0][0]]
									unit = " ".join([ptest[0][0], word])
									self.subordinate_strings[unit] = subostr

									self.used_unit_adjectives.append(ptest[0][0])
									conjunction = ((unit, tag), cst[1])
									self.conjunctions.append(conjunction)
									self.track(conjunction[0], "subordinate", self.subtype)
									do_std_unit = False
								else:
									if self.last_unit is None and self.last_context is not None:
										self.last_context = None
										lc = self.contexts.pop()
										unit = " ".join([lc, word])
									else:
										unit = " ".join([self.last_unit, word])
										self.units.pop()
										del p.unit_subtypes[self.last_unit]

									self.used_unit_adjectives.append(self.last_word)

							if do_std_unit:
								#rint "prec", unit
								unit, uidx = self.fix_unit(unit)
								#rint "postc", unit
								if not unit in p.units_acting_as_context or not p.units_acting_as_context[unit]:
									if self.last_unit and self.framing_question and len(self.operators) == 0 and self.last_unit != unit:
										context = unit
										if self.subtype[0] == "self":
											context = self.problem.brain.self_reflexive(context, True)
										# @TODO: This needs to be a subroutine or something
										self.last_context = context
										self.contexts.append(context)
										if self.is_relative_quantity and not self.comparator_context and self.main_context:
											self.comparator_context = context
											self.track(context, "comparator_context", self.subtype)
										else:
											self.main_context = context
											self.track(context, "context", self.subtype)
										p.context_subtypes[context] = self.subtype
									else:
										if len(self.operators) > 0 and self.last_unit and not self.main_context:
											if self.last_unit != unit:
												context = self.units.pop()
												del p.unit_subtypes[context]
												self.last_context = context
												self.contexts.append(context)
												if self.is_relative_quantity and not self.comparator_context and self.main_context:
													self.comparator_context = context
													self.track(context, "comparator_context", self.subtype, self.last_unit_index)
												else:
													self.main_context = context
													self.track(context, "context", self.subtype, self.last_unit_index)
												p.context_subtypes[context] = self.subtype
										self.last_unit = unit
										self.last_unit_tag = tag
										self.last_unit_index = len(self.parsed)
										self.units.append(unit)
										p.unit_subtypes[unit] = self.subtype
										#rint unit, "c"
										self.unit_idx[unit] = self.last_unit_index
										if self.new_units_as_context:
											p.units_acting_as_context[unit] = True
										self.track(unit, "unit", self.subtype, uidx)
								else:
									context = unit
									if self.subtype[0] == "self":
										context = self.problem.brain.self_reflexive(context, True)
									# @TODO: This needs to be a subroutine or something
									self.last_context = context
									self.contexts.append(context)
									if self.is_relative_quantity and not self.comparator_context and self.main_context:
										self.comparator_context = context
										self.track(context, "comparator_context", self.subtype, uidx)
									else:
										self.main_context = context
										self.track(context, "context", self.subtype, uidx)
									p.context_subtypes[context] = self.subtype

			if not did_something and self.subtype == None:
				self.subtype = self.get_subtype(word, tag)

			if tag == "SUB":
				conjunction = ((word, tag), self.last_conjunction)
				self.subordinate_strings[word] = " ".join(self.conjunction_parts)
				self.conjunction_parts = []
				self.conjunctions.append(conjunction)
				did_something = True
				self.track(conjunction[0], "subordinate", self.subtype)

			if tag == "PRP":
				if self.subtype and (self.subtype[0] == "self" or self.subtype[1] == "self"):
					context = word
					if self.subtype[0] == "self":
						context = self.problem.brain.self_reflexive(context, True)
					self.last_context = context
					self.contexts.append(context)
					did_something = True
					if self.is_relative_quantity and not self.comparator_context and self.main_context:
						self.comparator_context = context
						self.track(context, "comparator_context", self.subtype)
					else:
						self.main_context = context
						self.track(context, "context", self.subtype)
					p.context_subtypes[context] = self.subtype
				else:
					c = self.resolve_context(self.subtype)
					if c is None:
						c = self.resolve_context(self.subtype, compx=True)

					if c is not None:
						# If we're setting a relative quantity and the contexts are
						# the same we're not actually setting a relative quantity
						# we are simply indicating a mathematical operand
						if self.is_relative_quantity and c[0] == self.last_context:
							c2 = self.resolve_context(self.subtype, compx=True, failTest=True)
							if c2 is not None and c2[0] != self.last_context:
								c = c2
							else:
								self.is_relative_quantity = False
						did_something = True
						if self.is_relative_quantity and not self.comparator_context and self.main_context:
							self.comparator_context = c[0]
							self.track(c[0], "comparator_context", self.subtype, conv=True)
						else:
							self.main_context = c[0]
							self.track(c[0], "context", self.subtype)
						p.context_subtypes[c[0]] = self.subtype
						# Unset hanging conjunctions when we set a context
						self.last_conjunction = None
					else:
						if self.last_tag in ["IN"]:
							# remove the "of" in "of them"
							self.parsed.pop()
						# Assume this is a unit
						if not p.involves_acting or self.last_unit:
							unit, uidx = self.fix_unit(self.last_unit)
							self.last_unit = unit
							self.last_unit_tag = self.last_unit_tag
							self.last_unit_index = len(self.parsed)
							self.units.append(unit)
							p.unit_subtypes[unit] = self.subtype
							#rint unit, "d"
							self.unit_idx[unit] = self.last_unit_index
							if self.new_units_as_context:
								p.units_acting_as_context[unit] = True
							self.track(unit, "unit", self.subtype, uidx)

			if tag == "PRP$":
				if self.last_conjunction is not None:
					if self.is_relative_quantity and not self.comparator_context and self.main_context:
						c = self.resolve_context(self.subtype)
						ms = p.context_subtypes[self.main_context]
						if (not c or self.main_context != c[0]) and (not ms or self.subtype[0] != ms[0]):
							context = word
							if self.subtype[0] == "self":
								context = self.problem.brain.self_reflexive(context, True)
							did_something = True
							self.comparator_context = context
							self.track(word, "comparator_context", self.subtype, conv=True)
							self.last_conjunction = None
							self.conjunction_parts = []
							p.context_subtypes[word] = self.subtype

				if not did_something:
					did_something = True
					term = word
					st = self.subtype
					conval = self.resolve_context(self.subtype)
					if conval:
						term, st = conval
						term = ownerize(term)
					if self.subtype[0] == "self":
						term = self.problem.brain.self_reflexive(term, True)

					self.partial_context = term
					self.partial_subtype = st
					self.last_partial_context = self.track(term, "partial_context", st)

			if tag in ["NNP", "NNPS"]:
				if self.last_tag in ["NNP", "NNPS"]:
					# Last was partial context; the "Mrs." in "Mrs. Jones"
					self.last_context = None
					lc = self.contexts.pop()
					self.parsed.pop()
					if self.main_context == lc:
						self.main_context = None

					context = " ".join([lc, word])
					if self.is_relative_quantity and self.comparator_context == lc:
						self.comparator_context = context
					if self.subtype is not None and self.subtype[1] == "ambiguous":
						old = self.get_subtype(self.last_word, self.last_tag)
						self.subtype = (self.subtype[0], old[1])
				else:
					context = word
					if self.subtype[0] == "self":
						context = self.problem.brain.self_reflexive(context, True)
				self.last_context = context
				self.contexts.append(context)
				did_something = True
				if self.is_relative_quantity and not self.comparator_context and self.main_context:
					self.comparator_context = context
					self.track(context, "comparator_context", self.subtype)
				else:
					if not self.main_context:
						self.main_context = context
					self.track(context, "context", self.subtype)
				p.context_subtypes[context] = self.subtype

			if tag[:2] == "VB":
				if tag == "VB" and self.question:
					if self.last_verb_tag is not None:
						# VB*...VB indicates a question not an operation
						self.last_operator = None
						q_start = self.raw_operators.pop()
						st = self.get_subtype(self.last_verb, self.last_verb_tag)
						self.track(q_start, "q_start", st, self.last_verb)
						self.framing_question = False
						self.did_frame_question = True
						did_something = True
						self.track(word, "q_stop", self.subtype)
					elif self.framing_question:
						did_something = True
						self.framing_question = False
						self.did_frame_question = True
						self.track(word, "q_stop", self.subtype)
						op = p.brain.operator(word, self.sentence_text)
						if op == "ex":
							self.is_exchange = True
				elif tag != "VBG":
					if self.framing_question:
						did_something = True
						self.framing_question = False
						self.did_frame_question = True
						self.track(word, "q_stop", self.subtype)
					else:
						if not self.question and self.is_question and not self.did_frame_question:
							self.verb_question = True
							self.question = True
							self.phrasing_question = True
							self.framing_question = True
							did_something = True
							self.track(word, "asking", self.subtype)
						elif self.question and not self.did_frame_question:
							# We are asking a question and likely don't
							# need to invoke all the operator logic; this is
							# likely a "start the question" verb
							if not self.framing_question:
								did_something = True
								self.framing_question = True
								self.track(word, "q_start", self.subtype)
						else:
							op = p.brain.operator(word, self.sentence_text)
							if op not in [None, False]: # Retagged
								if op == "re":
									self.is_about_requirements = True
								if op == "ex":
									self.is_exchange = True
								self.last_verb_tag = tag
								self.last_verb = len(self.parsed)
								self.last_operator = word
								self.raw_operators.append(word)
								did_something = True
								self.operators.append(op)
								self.operator[word] = op
								self.subtype = self.get_subtype(word, tag)
								self.track(word, "operator", self.subtype)
							else:
								did_something = True
								process(word, tag)
				else:
					did_something = True
					gtype = p.brain.gerund(word, self.sentence_text)
					if gtype == "acting":
						self.acting = False
						self.actions.append(word)
						if self.main_context:
							p.context_actions[self.main_context] = (word, gtype, self.subtype)
					self.track(word, gtype, self.subtype)

			if tag in ["JJR", "COMP"]:
				did_something = True
				adj = p.brain.relative(word, self.sentence_text)
				self.is_relative_quantity = adj != "noise"
				self.track(word, adj, self.subtype)

			if tag in ["IN", "TO"]:
				self.last_conjunction = word
				self.last_conjunction_tag = tag
				self.conjunction_parts.append(word)
				did_something = True
				self.track(word, "conjunction", self.subtype)

			if tag in ["POS"]:
				did_something = True
				self.track(word, "possessive", self.subtype)

			if tag in [".", ","]:
				did_something = True
				self.track(word, "punctuation", self.subtype)

			if tag in ["$"]:
				did_something = True
				self.track(word, "money", "whole")

			if tag == "EX":
				did_something = True
				self.track(word, "exestential", self.subtype)
				self.problem.exestential = True

			if tag in ["CD", "LS"]: # A cardinal number
				if self.last_tag == "DT":
					if self.last_determiner == "constant":
						# should safely be able to ignore detemriner constant
						self.parsed.pop()
						self.last_determiner = None

				if self.last_conjunction is not None:
					self.conjunction_parts.pop()
				did_something = True
				if is_number(word):
					self.track(word, "constant", self.subtype)
				else:
					self.track(p.brain.number(word, self.sentence_text), "constant", self.subtype)

			if tag == "DT": # A determiner (the)
				did_something = True
				dtype = p.brain.determiner(word, self.sentence_text)
				self.last_determiner = dtype
				if dtype == "variable":
					vtype = p.brain.variable(word, self.sentence_text)
					if vtype == "dynamic_variable":
						do_dyn_var_trk = True
						if self.last_tag == "IN":
							do_dyn_var_trk = False
							process(word, "RB")
							return
						if do_dyn_var_trk:
							self.track(word, vtype, self.subtype)
					else:
						self.track(vtype, "variable_relationship", self.subtype)
					self.last_variable =  word
					self.last_variable_type = vtype
				elif dtype == "constant":
					self.track(p.brain.number(word, self.sentence_text), dtype, self.subtype)
				elif dtype == "noise":
					if self.is_question and self.phrasing_question:
						self.parsed.pop()
						did_something = True
						self.track(" ".join([self.last_word, word]), "asking", self.subtype)
				else:
					self.track(word, dtype, self.subtype)

			if tag == "RB": # An adverb, probably a subordinate?
				if self.verb_question and self.framing_question:
					tag = "JJ" # This is almost certainly not an adverb at this point
				else:
					if self.last_conjunction is not None:
						conjunction = ((word, tag), self.last_conjunction)
						self.last_conjunction = None
						self.subordinate_strings[word] = " ".join(self.conjunction_parts)
						self.conjunction_parts = []
					else:
						conjunction = ((word, tag), None)
						self.subordinate_strings[word] = word
					self.conjunctions.append(conjunction)
					did_something = True
					self.track(conjunction[0], "subordinate", self.subtype)

			# Anything about phrasing must come before the wh-determiner block
			if tag == "JJ": # Adjective
				if self.phrasing_question:
					self.parsed.pop()
					did_something = True
					self.track(" ".join([self.last_word, word]), "asking", self.subtype)
				elif self.last_tag in ["JJ"]:
					self.used_unit_adjectives.append(word)
					did_something = True
					self.last_adjective = " ".join([self.last_adjective, word])
					self.track(self.last_adjective, "adjective", self.subtype, self.last_adj_index)
				elif self.last_tag in ["IN"]:
					did_something = True
					unit = " ".join([self.last_unit, self.last_word, word])
					self.problem.descriptive_units.append(unit)
					self.problem.refined_units[self.last_unit] = unit
					self.units.pop()
					del p.unit_subtypes[self.last_unit]
					self.parsed.pop()
					self.parsed.pop()
					self.last_unit = unit
					self.last_unit_tag = tag
					self.last_unit_index = len(self.parsed)
					unit, uidx = self.fix_unit(unit)
					self.units.append(unit)
					p.unit_subtypes[unit] = self.subtype
					self.unit_idx[unit] = self.last_unit_index
					#rint unit, "e"
					if self.new_units_as_context:
						p.units_acting_as_context[unit] = True
					self.track(unit, "unit", self.subtype, uidx)
				else:
					self.used_unit_adjectives.append(word)
					did_something = True
					self.last_adjective = word
					self.last_adj_index = len(self.parsed)
					self.track(word, "adjective", self.subtype)

			if tag == "PIP":
				did_something = True
				self.track(word, "pre_ind_plu", self.subtype)
				if not self.problem.exestential:
					self.acting = True
					self.problem.involves_acting = True
					if self.last_unit is not None and self.last_context is None:
						# If we have a present indicitive plural with no context
						# it is likely that we're dealing with a context which has
						# been misinterpreted as a unit, so switch that
						# mistake here.
						p.units_acting_as_context[self.last_unit] = True

						# Remove the last unit and make it a context
						context = self.units.pop()
						del p.unit_subtypes[context]
						self.last_context = context
						self.contexts.append(context)
						if self.is_relative_quantity and not self.comparator_context and self.main_context:
							self.comparator_context = context
							self.track(context, "comparator_context", self.subtype, self.last_unit_index)
						else:
							self.main_context = context
							self.track(context, "context", self.subtype, self.last_unit_index)
						p.context_subtypes[context] = self.subtype

						# @TODO: This needs a much better tracking system
						self.last_unit = None
						self.last_unit_tag = None
						self.last_unit_index = -1
					elif not self.phrasing_question:
						self.new_units_as_context = True

			if tag in ["WRB", "WDT", "WP", "WP$"]: # Wh- determiner
				self.question = True
				self.phrasing_question = True
				did_something = True
				self.track(word, "asking", self.subtype)
			elif self.phrasing_question and not (tag[:2] == "VB" and self.is_question):
				self.phrasing_question = False

			if tag == "CC":
				did_something = True
				if self.verb_question and self.framing_question:
					self.track(word, "eval_option_sep")
				else:
					self.track(word, "coordinating_conjunction")

			if self.subtype is not None:
				did_something = True

			if not did_something:
				#rint "Answer Unknown", word, tag
				p.brain.unknown(word, tag, self.subtype, self.sentence_text)
				process(word, tag)

			self.last_word = word
			self.last_tag = tag
			self.last_subtype = self.subtype

		# Look before you leap
		for s_tag in self.sentence:
			word, tag = s_tag
			if tag == "." and word == "?":
				self.is_question = True

		for s_tag in self.sentence:
			process(*s_tag)
			self.index += 1

		if self.partial_context:
			context = self.partial_context
			idx = self.last_partial_context
			stype = self.partial_subtype

			self.partial_context = None
			self.last_partial_context = None
			self.partial_subtype = None

			if self.is_relative_quantity and not self.comparator_context and self.main_context:
				self.comparator_context = context
				self.track(context, "comparator_context", stype, idx, True)

		last_context = None
		last_possessive = None
		is_possessive = False
		was_possessive = False
		did_swap_context_for_unit = False
		reparsed = []
		# Walk this to combine context with their unit possessives
		for part in self.parsed:
			word, role, subtype = part
			if role == "context":
				if word in self.problem.units or (word != self.main_context and len(self.units) == 0):
					self.contexts.remove(word)
					role = "unit"
					self.units.append(word)
					did_swap_context_for_unit = True
				else:
					last_context = part
			elif last_context is not None and role == "possessive":
				last_possessive = word
				is_possessive = True
			elif role == "subordinate":
				if is_possessive and word[1][:2] == "NN":
					was_possessive = True
					cidx = self.contexts.index(last_context[0])
					con_to_rem = None
					for c in self.conjunctions:
						if c[0] == word:
							con_to_rem = c
							break
					if con_to_rem is not None:
						self.conjunctions.remove(con_to_rem)
					word = " ".join([last_context[0] + last_possessive, word[0]])
					subtype = last_context[2]
					role = "context"
					self.contexts[cidx] = word
					if self.main_context == last_context[0]:
						self.main_context = word
					last_context = None
					last_possessive = None
					is_possessive = False
					reparsed.pop()
					reparsed.pop()
			elif role == "unit":
				if is_possessive:
					was_possessive = True
					cidx = self.contexts.index(last_context[0])
					self.units.remove(word)
					word = " ".join([last_context[0] + last_possessive, word])
					subtype = last_context[2]
					role = "context"
					self.contexts[cidx] = word
					if self.main_context == last_context[0]:
						self.main_context = word
					last_context = None
					last_possessive = None
					is_possessive = False
					reparsed.pop()
					reparsed.pop()
				elif did_swap_context_for_unit:
					did_swap_context_for_unit = False
					self.units.remove(word)
					role = "context"
					self.contexts.append(word)
			reparsed.append((word, role, subtype))
		#rint self.sentence_text, "::::", self.main_context
		self.parsed = reparsed

		# Make all the inferred items unique
		self.raw_operators = uniq(self.raw_operators)
		self.contexts = uniq(self.contexts)
		self.units = uniq(self.units)
		self.actions = uniq(self.actions)
		self.operators = uniq(self.operators)

		text = self.sentence_text

		nunits = []
		for unit in self.units:
			acting_as_context = False
			if unit in p.units_acting_as_context:
				acting_as_context = p.units_acting_as_context[unit]

			# Units can be complicated by adjectives which break up the unit
			# into important subdivisions. However, these subdivisions may
			# also be simple detractors and not relevant to the actual string
			# match for the unit. As such, we split by any spaces and then
			# compile all possible formulations of the unit

			if not unit in self.problem.descriptive_units and " " in unit:
				parts = unit.split(" ")

				# The item is the last part of the unit
				item = parts.pop()
				for part in parts:
					nu = " ".join([part, item])
					nunits.append(nu)
	#				if acting_as_context:
	#					p.units_acting_as_context[nu] = True

		self.units = uniq(self.units + nunits)
		for unit in self.units:
			if unit in self.problem.refined_units:
				uxd = self.parsed[self.unit_idx[unit]]
				self.parsed[self.unit_idx[unit]] = (self.problem.refined_units[unit], uxd[1], uxd[2])

		# Resolve the subordinates
		for o in self.conjunctions:
			subordinate, conjunction = o
			outp = p.brain.subordinate(subordinate, text)
			self.subordinate_lookup[subordinate[0]] = outp
			if outp == "object":
				continue

			self.subordinates.append((subordinate[0], outp))
			if len(self.subordinate_strings[subordinate[0]]) == 0 and outp != "place_noun":
				self.subordinate_strings[subordinate[0]] = ANSWER_SUBORDINATE[outp]
			if outp == "context_grouping":
				csub = self.get_subtype(subordinate[0], subordinate[1])
				if csub:
					c = self.resolve_context(csub)
					if c:
						self.problem.subordinate_adaptive_contexts.append(c[0])
		self.subordinates = uniq(self.subordinates)
		self.problem.running_units += self.units
		self.problem.units += self.units
		self.problem.units = uniq(self.problem.units)

		if len(self.subordinates) > 0:
			if not self.main_context in self.problem.context_subordinates:
				self.problem.context_subordinates[self.main_context] = (self.subordinates, self.subordinate_strings, self.subordinate_subtypes, self.subordinate_lookup)
		elif self.main_context in self.problem.context_subordinates:
			# This is an inferred context
			self.subordinates, self.subordinate_strings, self.subordinate_subtypes, self.subordinate_lookup = self.problem.context_subordinates[self.main_context]
			for sub in self.subordinates:
				subord, subt = sub
				self.track(sub, "subordinate_inferred", self.subordinate_subtypes[subord])

		if not self.main_context and self.operator:
			if self.problem.last_contexts["last"]:
				context, subtype = self.problem.last_contexts["last"]
				self.main_context = context
				self.track(context, "context_inferred", subtype)

		#rint self.subordinates, self.main_context, self.problem.context_subordinates

		has_unit_proxy = False
		if self.main_context in self.problem.context_subordinates:
			if len(self.subordinates) == 0:
				# This is an inferred context
				self.subordinates, self.subordinate_strings, self.subordinate_subtypes, self.subordinate_lookup = self.problem.context_subordinates[self.main_context]
				for sub in self.subordinates:
					subord, subt = sub
					self.track(sub, "subordinate_inferred", self.subordinate_subtypes[subord])
			elif len(self.subordinates) > 0:
				subs, sub_strs, sub_subs, sub_look = self.problem.context_subordinates[self.main_context]
				handeled_subtypes = []
				for s in self.subordinate_lookup:
					st = self.subordinate_lookup[s]
					if st is not None:
						if st[0:4] == "time":
							st = st[0:4]
					handeled_subtypes.append(st)
				has_unit_proxy = "unit_grouping" in handeled_subtypes

				for sub in subs:
					subord, subt = sub
					st = subt
					if st is not None:
						if st == "costpay":
							continue
						if st[0:4] == "time":
							st = st[0:4]
						if st in handeled_subtypes and st == "time":
							continue
					if subord in self.subordinate_lookup:
						continue
					self.subordinate_subtypes[subord] = sub_subs[subord]
					self.subordinate_lookup[subord] = sub_look[subord]
					if subt != "refiner":
						self.subordinates.append(sub)
					self.track(sub, "subordinate_inferred", self.subordinate_subtypes[subord])

		if self.main_context in self.problem.context_actions and len(self.actions) == 0:
			word, gtype, subtype = self.problem.context_actions[self.main_context]
			self.track(word, gtype + "_inferred", subtype)

		if len(self.units) == 0 and len(self.problem.running_units) > 0 and not has_unit_proxy:
			iu = self.problem.running_units[-1]
			self.track(iu, "unit_inferred", self.problem.unit_subtypes[iu])

		if self.is_relative_quantity and self.comparator_context is None and self.main_context is not None:
			possible_comp = None
			for comp in self.problem.contexts:
				if comp != self.main_context:
					possible_comp = comp
					break
			if possible_comp is not None:
				self.track(possible_comp, "comparator_context_inferred", self.problem.context_subtypes[possible_comp], conv=True)

		self.problem.contexts += self.contexts
		self.problem.contexts = uniq(self.problem.contexts)

	def __str__(self):
		return self.sentence_text


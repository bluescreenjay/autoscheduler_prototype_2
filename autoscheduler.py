#!/usr/bin/env python3
"""
Auto-scheduling system for interviews using Google OR-Tools.

This system schedules group and individual interviews for applicants with recruiters
in available rooms, following all specified constraints.
"""

import csv
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
from collections import defaultdict
import json

try:
    from ortools.sat.python import cp_model
    HAS_ORTOOLS = True
except ImportError as e:
    HAS_ORTOOLS = False
    print(f"WARNING: OR-Tools import failed: {e}")
    print("Please install with: pip install ortools")


@dataclass
class TimeSlot:
    """Represents a time slot with start and end times."""
    start: datetime
    end: datetime
    
    def __str__(self):
        return f"{self.start.strftime('%m/%d %I:%M %p')}-{self.end.strftime('%I:%M %p')}"
    
    def overlaps(self, other: 'TimeSlot') -> bool:
        """Check if this time slot overlaps with another."""
        return self.start < other.end and other.start < self.end
    
    def duration_minutes(self) -> int:
        """Get duration in minutes."""
        return int((self.end - self.start).total_seconds() / 60)


@dataclass
class Applicant:
    """Represents an applicant with their information and availability."""
    id: str
    name: str
    email: str
    teams: List[str]
    availability: List[TimeSlot]


@dataclass
class Recruiter:
    """Represents a recruiter with their information and availability."""
    id: str
    name: str
    team: str
    availability: List[TimeSlot]


@dataclass
class Room:
    """Represents a room with its availability."""
    id: str
    availability: List[TimeSlot]


@dataclass
class Interview:
    """Represents a scheduled interview."""
    type: str  # 'group' or 'individual'
    time_slot: TimeSlot
    room: str
    applicants: List[str]
    recruiters: List[str]


class InterviewScheduler:
    """Main scheduler class using Google OR-Tools."""
    
    def __init__(self, inputs_dir: str, results_dir: str):
        self.inputs_dir = inputs_dir
        self.results_dir = results_dir
        self.applicants: Dict[str, Applicant] = {}
        self.recruiters: Dict[str, Recruiter] = {}
        self.rooms: Dict[str, Room] = {}
        self.time_slots: List[TimeSlot] = []
        self.scheduled_interviews: List[Interview] = []
        self.unscheduled_applicants: List[str] = []
        
        # Create results directory
        os.makedirs(results_dir, exist_ok=True)
        
    def load_data(self):
        """Load all input data from CSV files."""
        print("Loading input data...")
        self._load_applicants()
        self._load_recruiters()
        self._load_rooms()
        self._generate_time_slots()
        print(f"Loaded {len(self.applicants)} applicants, {len(self.recruiters)} recruiters, {len(self.rooms)} rooms")
        
    def _parse_time_string(self, time_str: str, date_str: str) -> datetime:
        """Parse time string like '5 PM - 6 PM' with a given date."""
        # Extract start time
        start_match = re.search(r'(\d+)\s*(AM|PM)', time_str)
        if start_match:
            hour = int(start_match.group(1))
            period = start_match.group(2)
            
            if period == 'PM' and hour != 12:
                hour += 12
            elif period == 'AM' and hour == 12:
                hour = 0
                
            # Parse date
            date_match = re.search(r'September (\d+), 2025', date_str)
            if date_match:
                day = int(date_match.group(1))
                return datetime(2025, 9, day, hour, 0)
        
        return None
        
    def _parse_availability_slot(self, slot_str: str, date_str: str) -> Optional[TimeSlot]:
        """Parse availability slot like '5 PM - 6 PM' for a given date."""
        parts = slot_str.strip().split(' - ')
        if len(parts) != 2:
            return None
            
        start_str, end_str = parts
        start_time = self._parse_time_string(start_str, date_str)
        end_time = self._parse_time_string(end_str, date_str)
        
        if start_time and end_time:
            return TimeSlot(start_time, end_time)
        return None
        
    def _load_applicants(self):
        """Load applicant data from CSV."""
        filepath = os.path.join(self.inputs_dir, 'applicant_information.csv')
        
        with open(filepath, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                applicant_id = row['Email Address'].split('@')[0]  # Use email prefix as ID
                name = row['First and Last Name']
                email = row['Email Address']
                
                # Parse teams
                teams_str = row['Select the teams are you interested in joining:']
                teams = []
                if 'Astra' in teams_str:
                    teams.append('Astra')
                if 'Juvo' in teams_str:
                    teams.append('Juvo')
                if 'Infinitum' in teams_str:
                    teams.append('Infinitum')
                if 'Terra' in teams_str:
                    teams.append('Terra')
                
                # Parse availability
                availability = []
                date_columns = [
                    'Thursday, September 11, 2025',
                    'Friday, September 12, 2025', 
                    'Saturday, September 13, 2025',
                    'Sunday, September 14, 2025',
                    'Monday, September 15, 2025'
                ]
                
                for date_col in date_columns:
                    if date_col in row and row[date_col]:
                        slots_str = row[date_col]
                        for slot_str in slots_str.split(','):
                            slot = self._parse_availability_slot(slot_str.strip(), date_col)
                            if slot:
                                availability.append(slot)
                
                self.applicants[applicant_id] = Applicant(
                    id=applicant_id,
                    name=name,
                    email=email,
                    teams=teams,
                    availability=availability
                )
                
    def _parse_recruiter_datetime(self, datetime_str: str) -> Optional[TimeSlot]:
        """Parse recruiter datetime string like '2025-09-11 17:00-21:00'."""
        try:
            date_part, time_part = datetime_str.split(' ')
            start_time_str, end_time_str = time_part.split('-')
            
            # Parse date
            year, month, day = map(int, date_part.split('-'))
            
            # Parse start time
            start_hour, start_min = map(int, start_time_str.split(':'))
            start_dt = datetime(year, month, day, start_hour, start_min)
            
            # Parse end time
            end_hour, end_min = map(int, end_time_str.split(':'))
            end_dt = datetime(year, month, day, end_hour, end_min)
            
            return TimeSlot(start_dt, end_dt)
        except:
            return None
            
    def _load_recruiters(self):
        """Load recruiter data from CSV."""
        filepath = os.path.join(self.inputs_dir, 'recruiters.csv')
        
        with open(filepath, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                recruiter_id = row['recruiter_id']
                name = row['recruiter_name']
                team = row['team']
                
                # Parse availability
                availability = []
                if row['availability']:
                    for slot_str in row['availability'].split(';'):
                        slot = self._parse_recruiter_datetime(slot_str.strip())
                        if slot:
                            availability.append(slot)
                
                self.recruiters[recruiter_id] = Recruiter(
                    id=recruiter_id,
                    name=name,
                    team=team,
                    availability=availability
                )
                
    def _parse_room_availability(self, avail_str: str) -> List[TimeSlot]:
        """Parse room availability string."""
        availability = []
        
        # Split by semicolon for different date ranges
        for date_range in avail_str.split(';'):
            date_range = date_range.strip()
            
            # Parse format like "Sep 11 2025 5pm-9pm"
            match = re.match(r'Sep (\d+) 2025 (\d+)(am|pm)-(\d+)(am|pm)', date_range)
            if match:
                day = int(match.group(1))
                start_hour = int(match.group(2))
                start_period = match.group(3)
                end_hour = int(match.group(4))
                end_period = match.group(5)
                
                # Convert to 24-hour format
                if start_period == 'pm' and start_hour != 12:
                    start_hour += 12
                elif start_period == 'am' and start_hour == 12:
                    start_hour = 0
                    
                if end_period == 'pm' and end_hour != 12:
                    end_hour += 12
                elif end_period == 'am' and end_hour == 12:
                    end_hour = 0
                
                start_dt = datetime(2025, 9, day, start_hour, 0)
                end_dt = datetime(2025, 9, day, end_hour, 0)
                
                availability.append(TimeSlot(start_dt, end_dt))
                
        return availability
        
    def _load_rooms(self):
        """Load room data from CSV."""
        filepath = os.path.join(self.inputs_dir, 'rooms.csv')
        
        with open(filepath, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                room_id = row['room_id']
                availability = self._parse_room_availability(row['availability'])
                
                self.rooms[room_id] = Room(
                    id=room_id,
                    availability=availability
                )
                
    def _generate_time_slots(self):
        """Generate all possible 20-minute time slots."""
        # Define the interview periods
        dates_and_hours = [
            (datetime(2025, 9, 11), 17, 21),  # Sep 11: 5pm-9pm
            (datetime(2025, 9, 12), 17, 21),  # Sep 12: 5pm-9pm
            (datetime(2025, 9, 13), 9, 21),   # Sep 13: 9am-9pm
            (datetime(2025, 9, 14), 9, 21),   # Sep 14: 9am-9pm
            (datetime(2025, 9, 15), 17, 21),  # Sep 15: 5pm-9pm
        ]
        
        for date, start_hour, end_hour in dates_and_hours:
            current_time = date.replace(hour=start_hour, minute=0)
            end_time = date.replace(hour=end_hour, minute=0)
            
            while current_time < end_time:
                slot_end = current_time + timedelta(minutes=20)
                if slot_end <= end_time:
                    self.time_slots.append(TimeSlot(current_time, slot_end))
                current_time += timedelta(minutes=20)
                
        print(f"Generated {len(self.time_slots)} possible 20-minute time slots")
        
    def schedule_interviews(self):
        """Main scheduling function using OR-Tools."""
        if not HAS_ORTOOLS:
            print("ERROR: OR-Tools is required but not installed.")
            return False
            
        print("Starting interview scheduling...")
        
        # First pass: Strict scheduling
        success = self._schedule_with_constraints(strict=True)
        
        # Second pass: Relaxed scheduling for unscheduled applicants
        if self.unscheduled_applicants:
            print(f"\nFirst pass complete. {len(self.unscheduled_applicants)} applicants unscheduled.")
            print("Starting relaxed scheduling...")
            self._schedule_with_constraints(strict=False)
            
        return success
        
    def _schedule_with_constraints(self, strict: bool = True) -> bool:
        """Schedule interviews with or without strict constraints."""
        model = cp_model.CpModel()
        
        # Get applicants to schedule
        if strict:
            applicants_to_schedule = list(self.applicants.keys())
        else:
            applicants_to_schedule = self.unscheduled_applicants.copy()
            
        if not applicants_to_schedule:
            return True
            
        print(f"Scheduling {len(applicants_to_schedule)} applicants...")
        
        # Variables: interview assignments
        # group_interviews[applicant][time][room] = 1 if applicant has group interview at time in room
        group_interviews = {}
        individual_interviews = {}
        
        for applicant_id in applicants_to_schedule:
            group_interviews[applicant_id] = {}
            individual_interviews[applicant_id] = {}
            
            for i, time_slot in enumerate(self.time_slots):
                group_interviews[applicant_id][i] = {}
                individual_interviews[applicant_id][i] = {}
                
                for room_id in self.rooms:
                    group_interviews[applicant_id][i][room_id] = model.NewBoolVar(
                        f'group_{applicant_id}_{i}_{room_id}'
                    )
                    individual_interviews[applicant_id][i][room_id] = model.NewBoolVar(
                        f'individual_{applicant_id}_{i}_{room_id}'
                    )
        
        # Recruiter assignment variables
        # recruiter_group[recruiter][time][room] = 1 if recruiter is in group interview
        recruiter_group = {}
        recruiter_individual = {}
        
        for recruiter_id in self.recruiters:
            recruiter_group[recruiter_id] = {}
            recruiter_individual[recruiter_id] = {}
            
            for i, time_slot in enumerate(self.time_slots):
                recruiter_group[recruiter_id][i] = {}
                recruiter_individual[recruiter_id][i] = {}
                
                for room_id in self.rooms:
                    recruiter_group[recruiter_id][i][room_id] = model.NewBoolVar(
                        f'rec_group_{recruiter_id}_{i}_{room_id}'
                    )
                    recruiter_individual[recruiter_id][i][room_id] = model.NewBoolVar(
                        f'rec_individual_{recruiter_id}_{i}_{room_id}'
                    )
        
        # CONSTRAINTS
        
        # 1. Each applicant must have exactly one group interview and one individual interview
        for applicant_id in applicants_to_schedule:
            # Exactly one group interview
            model.Add(
                sum(group_interviews[applicant_id][i][room_id] 
                    for i in range(len(self.time_slots))
                    for room_id in self.rooms) == 1
            )
            
            # Exactly one individual interview  
            model.Add(
                sum(individual_interviews[applicant_id][i][room_id]
                    for i in range(len(self.time_slots))
                    for room_id in self.rooms) == 1
            )
        
        # 2. Room capacity: only one interview per room per time slot
        for i, time_slot in enumerate(self.time_slots):
            for room_id in self.rooms:
                # Can't have both group and individual in same room at same time
                model.Add(
                    sum(group_interviews[applicant_id][i][room_id] 
                        for applicant_id in applicants_to_schedule) +
                    sum(individual_interviews[applicant_id][i][room_id]
                        for applicant_id in applicants_to_schedule) <= 1
                )
        
        # 3. Availability constraints
        self._add_availability_constraints(model, group_interviews, individual_interviews, 
                                         recruiter_group, recruiter_individual, 
                                         applicants_to_schedule, strict)
        
        # 4. Group interview constraints
        self._add_group_interview_constraints(model, group_interviews, recruiter_group, 
                                            applicants_to_schedule, strict)
        
        # 5. Time proximity constraints (group and individual interviews close together)
        if strict:
            self._add_time_proximity_constraints(model, group_interviews, individual_interviews,
                                               applicants_to_schedule)
        
        # 6. Team matching for individual interviews
        self._add_team_matching_constraints(model, individual_interviews, recruiter_individual,
                                          applicants_to_schedule, strict)
        
        # Solve the model
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 300.0  # 5 minute timeout
        
        print("Solving optimization model...")
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print(f"Solution found! Status: {'OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE'}")
            self._extract_solution(solver, group_interviews, individual_interviews,
                                 recruiter_group, recruiter_individual, applicants_to_schedule)
            return True
        else:
            print(f"No solution found. Status: {status}")
            if strict:
                self.unscheduled_applicants = applicants_to_schedule.copy()
            return False
            
    def _add_availability_constraints(self, model, group_interviews, individual_interviews,
                                    recruiter_group, recruiter_individual, applicants_to_schedule, strict):
        """Add availability constraints for applicants and recruiters."""
        
        # Applicant availability
        for applicant_id in applicants_to_schedule:
            applicant = self.applicants[applicant_id]
            
            for i, time_slot in enumerate(self.time_slots):
                # Check if applicant is available at this time
                available = any(
                    slot.start <= time_slot.start and time_slot.end <= slot.end
                    for slot in applicant.availability
                )
                
                if not available:
                    # Force to 0 if not available
                    for room_id in self.rooms:
                        model.Add(group_interviews[applicant_id][i][room_id] == 0)
                        model.Add(individual_interviews[applicant_id][i][room_id] == 0)
        
        # Recruiter availability
        for recruiter_id in self.recruiters:
            recruiter = self.recruiters[recruiter_id]
            
            for i, time_slot in enumerate(self.time_slots):
                # Check if recruiter is available at this time
                available = any(
                    slot.start <= time_slot.start and time_slot.end <= slot.end
                    for slot in recruiter.availability
                )
                
                if not available:
                    # Force to 0 if not available
                    for room_id in self.rooms:
                        model.Add(recruiter_group[recruiter_id][i][room_id] == 0)
                        model.Add(recruiter_individual[recruiter_id][i][room_id] == 0)
        
        # Room availability
        for room_id in self.rooms:
            room = self.rooms[room_id]
            
            for i, time_slot in enumerate(self.time_slots):
                # Check if room is available at this time
                available = any(
                    slot.start <= time_slot.start and time_slot.end <= slot.end
                    for slot in room.availability
                )
                
                if not available:
                    # Force to 0 if room not available
                    for applicant_id in applicants_to_schedule:
                        model.Add(group_interviews[applicant_id][i][room_id] == 0)
                        model.Add(individual_interviews[applicant_id][i][room_id] == 0)
                        
    def _add_group_interview_constraints(self, model, group_interviews, recruiter_group, 
                                       applicants_to_schedule, strict):
        """Add constraints for group interviews."""
        
        for i, time_slot in enumerate(self.time_slots):
            for room_id in self.rooms:
                # If there's a group interview in this room at this time
                group_happening = model.NewBoolVar(f'group_happening_{i}_{room_id}')
                
                # Group happening if any applicant has group interview here
                applicants_in_group = [group_interviews[applicant_id][i][room_id] 
                                     for applicant_id in applicants_to_schedule]
                
                if applicants_in_group:
                    model.Add(group_happening == 1).OnlyEnforceIf(applicants_in_group)
                    model.Add(group_happening == 0).OnlyEnforceIf([v.Not() for v in applicants_in_group])
                    
                    # If group happening, must have 4-8 applicants
                    model.Add(sum(applicants_in_group) >= 4).OnlyEnforceIf(group_happening)
                    model.Add(sum(applicants_in_group) <= 8).OnlyEnforceIf(group_happening)
                    
                    # If group happening, must have at least 4 recruiters
                    recruiters_in_group = [recruiter_group[recruiter_id][i][room_id]
                                         for recruiter_id in self.recruiters]
                    model.Add(sum(recruiters_in_group) >= 4).OnlyEnforceIf(group_happening)
                    
                    # If strict, try to ensure recruiters from different teams
                    if strict:
                        self._add_diverse_recruiter_constraints(model, recruiter_group, i, room_id, group_happening)
                        
    def _add_diverse_recruiter_constraints(self, model, recruiter_group, time_index, room_id, group_happening):
        """Add constraints to ensure recruiters from different teams in group interviews."""
        teams = {'Astra', 'Juvo', 'Infinitum', 'Terra'}
        
        for team in teams:
            team_recruiters = [recruiter_id for recruiter_id, recruiter in self.recruiters.items() 
                             if recruiter.team == team or recruiter.team == 'All']
            
            if team_recruiters:
                # At least one recruiter from this team (or All team) in group interview
                team_representation = [recruiter_group[recruiter_id][time_index][room_id] 
                                     for recruiter_id in team_recruiters]
                model.Add(sum(team_representation) >= 1).OnlyEnforceIf(group_happening)
                
    def _add_time_proximity_constraints(self, model, group_interviews, individual_interviews, 
                                      applicants_to_schedule):
        """Add constraints to keep group and individual interviews close in time."""
        
        for applicant_id in applicants_to_schedule:
            # Create variables for interview times
            group_time = model.NewIntVar(0, len(self.time_slots) - 1, f'group_time_{applicant_id}')
            individual_time = model.NewIntVar(0, len(self.time_slots) - 1, f'individual_time_{applicant_id}')
            
            # Link time variables to interview assignments
            for i in range(len(self.time_slots)):
                for room_id in self.rooms:
                    model.Add(group_time == i).OnlyEnforceIf(group_interviews[applicant_id][i][room_id])
                    model.Add(individual_time == i).OnlyEnforceIf(individual_interviews[applicant_id][i][room_id])
            
            # Time difference constraint (prefer less than 2 time slots = 40 minutes apart)
            time_diff = model.NewIntVar(-len(self.time_slots), len(self.time_slots), f'time_diff_{applicant_id}')
            model.Add(time_diff == individual_time - group_time)
            
            # Prefer interviews within 4.5 time slots (90 minutes) of each other
            model.Add(time_diff >= -4)
            model.Add(time_diff <= 4)
            
    def _add_team_matching_constraints(self, model, individual_interviews, recruiter_individual,
                                     applicants_to_schedule, strict):
        """Add constraints to match recruiters with applicants' team interests."""
        
        for applicant_id in applicants_to_schedule:
            applicant = self.applicants[applicant_id]
            
            for i, time_slot in enumerate(self.time_slots):
                for room_id in self.rooms:
                    # If applicant has individual interview at this time/room
                    interview_happening = individual_interviews[applicant_id][i][room_id]
                    
                    if strict:
                        # Must have recruiter from one of applicant's interested teams
                        compatible_recruiters = []
                        for recruiter_id, recruiter in self.recruiters.items():
                            if recruiter.team in applicant.teams or recruiter.team == 'All':
                                compatible_recruiters.append(recruiter_individual[recruiter_id][i][room_id])
                        
                        if compatible_recruiters:
                            model.Add(sum(compatible_recruiters) >= 1).OnlyEnforceIf(interview_happening)
                    
                    # Exactly one recruiter in individual interview
                    recruiters_here = [recruiter_individual[recruiter_id][i][room_id] 
                                     for recruiter_id in self.recruiters]
                    model.Add(sum(recruiters_here) == 1).OnlyEnforceIf(interview_happening)
                    model.Add(sum(recruiters_here) == 0).OnlyEnforceIf(interview_happening.Not())
                    
    def _extract_solution(self, solver, group_interviews, individual_interviews,
                         recruiter_group, recruiter_individual, applicants_to_schedule):
        """Extract the solution from the solver."""
        
        scheduled_this_round = []
        
        for applicant_id in applicants_to_schedule:
            group_scheduled = False
            individual_scheduled = False
            
            # Find group interview
            for i, time_slot in enumerate(self.time_slots):
                for room_id in self.rooms:
                    if solver.Value(group_interviews[applicant_id][i][room_id]):
                        # Find all applicants and recruiters in this group interview
                        group_applicants = []
                        group_recruiters = []
                        
                        for other_applicant in applicants_to_schedule:
                            if solver.Value(group_interviews[other_applicant][i][room_id]):
                                group_applicants.append(other_applicant)
                                
                        for recruiter_id in self.recruiters:
                            if solver.Value(recruiter_group[recruiter_id][i][room_id]):
                                group_recruiters.append(recruiter_id)
                        
                        # Create group interview for 40 minutes
                        group_end_time = time_slot.start + timedelta(minutes=40)
                        group_slot = TimeSlot(time_slot.start, group_end_time)
                        
                        interview = Interview(
                            type='group',
                            time_slot=group_slot,
                            room=room_id,
                            applicants=group_applicants,
                            recruiters=group_recruiters
                        )
                        
                        # Only add once (for the first applicant found)
                        if not any(existing.type == 'group' and 
                                 existing.time_slot.start == group_slot.start and
                                 existing.room == room_id
                                 for existing in self.scheduled_interviews):
                            self.scheduled_interviews.append(interview)
                        
                        group_scheduled = True
                        break
                if group_scheduled:
                    break
            
            # Find individual interview
            for i, time_slot in enumerate(self.time_slots):
                for room_id in self.rooms:
                    if solver.Value(individual_interviews[applicant_id][i][room_id]):
                        # Find recruiter for this individual interview
                        individual_recruiters = []
                        
                        for recruiter_id in self.recruiters:
                            if solver.Value(recruiter_individual[recruiter_id][i][room_id]):
                                individual_recruiters.append(recruiter_id)
                        
                        interview = Interview(
                            type='individual',
                            time_slot=time_slot,
                            room=room_id,
                            applicants=[applicant_id],
                            recruiters=individual_recruiters
                        )
                        
                        self.scheduled_interviews.append(interview)
                        individual_scheduled = True
                        break
                if individual_scheduled:
                    break
            
            if group_scheduled and individual_scheduled:
                scheduled_this_round.append(applicant_id)
        
        # Update unscheduled list
        self.unscheduled_applicants = [
            applicant_id for applicant_id in applicants_to_schedule 
            if applicant_id not in scheduled_this_round
        ]
        
        print(f"Scheduled {len(scheduled_this_round)} applicants in this round")
        print(f"Remaining unscheduled: {len(self.unscheduled_applicants)}")
        
    def generate_reports(self):
        """Generate all required reports."""
        print("\nGenerating reports...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = os.path.join(self.results_dir, f"run_{timestamp}")
        os.makedirs(run_dir, exist_ok=True)
        
        # Generate all reports
        self._generate_main_schedule(run_dir)
        self._generate_unscheduled_report(run_dir)
        self._generate_block_breakdown(run_dir)
        self._generate_recruiter_schedule(run_dir)
        self._generate_applicant_schedule(run_dir)
        self._generate_summary_report(run_dir)
        
        print(f"Reports generated in: {run_dir}")
        return run_dir
        
    def _generate_main_schedule(self, output_dir):
        """Generate the main schedule file."""
        filepath = os.path.join(output_dir, 'main_schedule.csv')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Type', 'Start Time', 'End Time', 'Room', 'Applicants', 'Recruiters'])
            
            # Sort interviews by time
            sorted_interviews = sorted(self.scheduled_interviews, key=lambda x: x.time_slot.start)
            
            for interview in sorted_interviews:
                applicant_names = [self.applicants[app_id].name for app_id in interview.applicants]
                recruiter_names = [self.recruiters[rec_id].name for rec_id in interview.recruiters]
                
                writer.writerow([
                    interview.type,
                    interview.time_slot.start.strftime('%m/%d/%Y %I:%M %p'),
                    interview.time_slot.end.strftime('%m/%d/%Y %I:%M %p'),
                    interview.room,
                    '; '.join(applicant_names),
                    '; '.join(recruiter_names)
                ])
                
    def _generate_unscheduled_report(self, output_dir):
        """Generate report of unscheduled applicants."""
        filepath = os.path.join(output_dir, 'unscheduled_applicants.csv')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Applicant ID', 'Name', 'Email', 'Teams Interested'])
            
            for applicant_id in self.unscheduled_applicants:
                applicant = self.applicants[applicant_id]
                writer.writerow([
                    applicant_id,
                    applicant.name,
                    applicant.email,
                    '; '.join(applicant.teams)
                ])
                
    def _generate_block_breakdown(self, output_dir):
        """Generate block breakdown for admins."""
        filepath = os.path.join(output_dir, 'block_breakdown.txt')
        
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write("INTERVIEW BLOCK BREAKDOWN\n")
            file.write("=" * 50 + "\n\n")
            
            # Group by time slots
            time_blocks = defaultdict(list)
            for interview in self.scheduled_interviews:
                time_key = interview.time_slot.start.strftime('%m/%d/%Y %I:%M %p')
                time_blocks[time_key].append(interview)
            
            for time_key in sorted(time_blocks.keys()):
                file.write(f"TIME BLOCK: {time_key}\n")
                file.write("-" * 30 + "\n")
                
                for interview in time_blocks[time_key]:
                    file.write(f"  {interview.type.upper()} INTERVIEW - Room {interview.room}\n")
                    
                    applicant_names = [self.applicants[app_id].name for app_id in interview.applicants]
                    file.write(f"    Applicants: {', '.join(applicant_names)}\n")
                    
                    recruiter_names = [self.recruiters[rec_id].name for rec_id in interview.recruiters]
                    file.write(f"    Recruiters: {', '.join(recruiter_names)}\n")
                    file.write("\n")
                
                file.write("\n")
                
    def _generate_recruiter_schedule(self, output_dir):
        """Generate individual schedules for each recruiter."""
        filepath = os.path.join(output_dir, 'recruiter_schedules.csv')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Recruiter', 'Start Time', 'End Time', 'Room', 'Interview Type', 'Applicants'])
            
            # Organize by recruiter
            recruiter_schedules = defaultdict(list)
            for interview in self.scheduled_interviews:
                for recruiter_id in interview.recruiters:
                    recruiter_schedules[recruiter_id].append(interview)
            
            for recruiter_id in sorted(recruiter_schedules.keys()):
                recruiter = self.recruiters[recruiter_id]
                interviews = sorted(recruiter_schedules[recruiter_id], key=lambda x: x.time_slot.start)
                
                for interview in interviews:
                    applicant_names = [self.applicants[app_id].name for app_id in interview.applicants]
                    
                    writer.writerow([
                        recruiter.name,
                        interview.time_slot.start.strftime('%m/%d/%Y %I:%M %p'),
                        interview.time_slot.end.strftime('%m/%d/%Y %I:%M %p'),
                        interview.room,
                        interview.type,
                        '; '.join(applicant_names)
                    ])
                    
    def _generate_applicant_schedule(self, output_dir):
        """Generate individual schedules for each applicant."""
        filepath = os.path.join(output_dir, 'applicant_schedules.csv')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Applicant', 'Start Time', 'End Time', 'Room', 'Interview Type', 'Recruiters'])
            
            # Organize by applicant
            applicant_schedules = defaultdict(list)
            for interview in self.scheduled_interviews:
                for applicant_id in interview.applicants:
                    applicant_schedules[applicant_id].append(interview)
            
            for applicant_id in sorted(applicant_schedules.keys()):
                applicant = self.applicants[applicant_id]
                interviews = sorted(applicant_schedules[applicant_id], key=lambda x: x.time_slot.start)
                
                for interview in interviews:
                    recruiter_names = [self.recruiters[rec_id].name for rec_id in interview.recruiters]
                    
                    writer.writerow([
                        applicant.name,
                        interview.time_slot.start.strftime('%m/%d/%Y %I:%M %p'),
                        interview.time_slot.end.strftime('%m/%d/%Y %I:%M %p'),
                        interview.room,
                        interview.type,
                        '; '.join(recruiter_names)
                    ])
                    
    def _generate_summary_report(self, output_dir):
        """Generate summary report."""
        filepath = os.path.join(output_dir, 'summary_report.txt')
        
        total_applicants = len(self.applicants)
        scheduled_applicants = total_applicants - len(self.unscheduled_applicants)
        success_rate = (scheduled_applicants / total_applicants) * 100 if total_applicants > 0 else 0
        
        group_interviews = len([i for i in self.scheduled_interviews if i.type == 'group'])
        individual_interviews = len([i for i in self.scheduled_interviews if i.type == 'individual'])
        
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write("INTERVIEW SCHEDULING SUMMARY REPORT\n")
            file.write("=" * 50 + "\n\n")
            
            file.write(f"Total Applicants: {total_applicants}\n")
            file.write(f"Successfully Scheduled: {scheduled_applicants}\n")
            file.write(f"Unscheduled: {len(self.unscheduled_applicants)}\n")
            file.write(f"Success Rate: {success_rate:.1f}%\n\n")
            
            file.write(f"Total Interviews Scheduled: {len(self.scheduled_interviews)}\n")
            file.write(f"Group Interviews: {group_interviews}\n")
            file.write(f"Individual Interviews: {individual_interviews}\n\n")
            
            file.write("SCHEDULING CONSTRAINTS:\n")
            file.write("- Each applicant needs 1 group + 1 individual interview\n")
            file.write("- Group interviews: 40 minutes, 4+ recruiters, 4-8 applicants\n")
            file.write("- Individual interviews: 20 minutes, 1 recruiter, 1 applicant\n")
            file.write("- Interviews should be within 90 minutes of each other\n")
            file.write("- Recruiters matched to applicant team interests\n\n")
            
            if self.unscheduled_applicants:
                file.write("UNSCHEDULED APPLICANTS:\n")
                for applicant_id in self.unscheduled_applicants:
                    applicant = self.applicants[applicant_id]
                    file.write(f"- {applicant.name} ({'; '.join(applicant.teams)})\n")


def main():
    """Main function to run the autoscheduler."""
    inputs_dir = "inputs"
    results_dir = "results"
    
    print("=== LUMA Interview Auto-Scheduler ===")
    print()
    
    # Check if OR-Tools is available
    if not HAS_ORTOOLS:
        print("ERROR: Google OR-Tools is required but not installed.")
        print("Please install with: pip install ortools")
        return
    
    # Initialize scheduler
    scheduler = InterviewScheduler(inputs_dir, results_dir)
    
    # Load data
    try:
        scheduler.load_data()
    except Exception as e:
        print(f"ERROR loading data: {e}")
        return
    
    # Schedule interviews
    try:
        success = scheduler.schedule_interviews()
        if not success and not scheduler.scheduled_interviews:
            print("ERROR: Could not schedule any interviews. Please check constraints and availability.")
            return
    except Exception as e:
        print(f"ERROR during scheduling: {e}")
        return
    
    # Generate reports
    try:
        output_dir = scheduler.generate_reports()
        print(f"\nScheduling complete! Check results in: {output_dir}")
    except Exception as e:
        print(f"ERROR generating reports: {e}")
        return


if __name__ == "__main__":
    main()

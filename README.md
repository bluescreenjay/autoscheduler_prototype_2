# LUMA Interview Auto-Scheduler

An automated interview scheduling system that optimally assigns applicants to group and individual interviews with recruiters in available rooms.

## Overview

This system schedules interviews for the period September 11-15, 2025, with the following time windows:
- September 11, 12, 15: 5:00 PM - 9:00 PM
- September 13, 14: 9:00 AM - 9:00 PM

## Requirements

### Software Dependencies
- Python 3.7 or higher
- Google OR-Tools: `pip install ortools`

### Input Files
The system requires three CSV files in the `inputs/` directory:

1. **applicant_information.csv** - Contains applicant data with columns:
   - Email Address
   - First and Last Name
   - Select the teams are you interested in joining
   - Thursday, September 11, 2025 (availability)
   - Friday, September 12, 2025 (availability)
   - Saturday, September 13, 2025 (availability)
   - Sunday, September 14, 2025 (availability)
   - Monday, September 15, 2025 (availability)

2. **recruiters.csv** - Contains recruiter data with columns:
   - recruiter_id
   - recruiter_name
   - team (Astra, Juvo, Infinitum, Terra, or All)
   - availability (format: YYYY-MM-DD HH:MM-HH:MM;...)

3. **rooms.csv** - Contains room data with columns:
   - room_id
   - availability (format: Sep DD YYYY HHam/pm-HHam/pm;...)

## Installation

1. Clone or download the autoscheduler files
2. Install required dependencies:
   ```
   pip install ortools
   ```
3. Ensure input CSV files are properly formatted in the `inputs/` directory

## Usage

Run the autoscheduler from the command line:

```
python autoscheduler.py
```

The system will:
1. Load all input data from CSV files
2. Generate possible time slots in 20-minute intervals
3. Run optimization to schedule interviews with strict constraints
4. Run relaxed optimization for any unscheduled applicants
5. Generate comprehensive reports in a timestamped results directory

## Scheduling Constraints

### Required Constraints
- Each applicant must have exactly one group interview and one individual interview
- Only one interview can occur in a room at any given time
- Group interviews last 40 minutes and require 4+ recruiters and 4-8 applicants
- Individual interviews last 20 minutes and require 1 recruiter and 1 applicant
- Group and individual interviews for the same applicant should be within 90 minutes of each other

### Preferred Constraints
- Group interview recruiters should represent different teams when possible
- Individual interview recruiters should be from teams the applicant is interested in
- Applicants in group interviews should represent diverse team interests

## Output Reports

The system generates a timestamped results directory containing:

1. **main_schedule.csv** - Complete schedule of all interviews
2. **unscheduled_applicants.csv** - List of applicants who could not be scheduled
3. **block_breakdown.txt** - Readable breakdown by time blocks for administrators
4. **recruiter_schedules.csv** - Individual schedules for each recruiter
5. **applicant_schedules.csv** - Individual schedules for each applicant
6. **summary_report.txt** - Overall scheduling statistics and success rate

## Scheduling Algorithm

The system uses Google OR-Tools constraint programming solver with a two-phase approach:

### Phase 1: Strict Scheduling
Attempts to schedule all applicants while maintaining all constraints including:
- Team diversity in group interviews
- Recruiter-applicant team matching
- Time proximity requirements

### Phase 2: Relaxed Scheduling
For any unscheduled applicants, relaxes some preferred constraints while maintaining:
- Core availability constraints
- Interview duration requirements
- Room capacity limits

## Troubleshooting

### Common Issues

**Import Error for OR-Tools:**
- Install OR-Tools: `pip install ortools`
- Ensure Python version compatibility (3.7+)

**No Applicants Scheduled:**
- Check that availability data is properly formatted
- Verify recruiters have sufficient availability
- Ensure room availability matches interview time windows

**Poor Scheduling Success Rate:**
- Increase recruiter availability
- Add more rooms
- Reduce time proximity constraints in relaxed phase

### Data Format Requirements

**Time Format in applicant_information.csv:**
- Use format: "5 PM - 6 PM, 7 PM - 8 PM"
- Separate multiple time slots with commas

**Date Format in recruiters.csv:**
- Use format: "2025-09-11 17:00-21:00;2025-09-12 17:00-21:00"
- Separate multiple date ranges with semicolons

**Room Availability Format:**
- Use format: "Sep 11 2025 5pm-9pm; Sep 12 2025 5pm-9pm"
- Separate multiple periods with semicolons

## Technical Details

The scheduler uses constraint programming to solve a complex optimization problem with hundreds of variables and constraints. The solver attempts to find an optimal solution within a 5-minute time limit for each phase.

Variable types include:
- Binary variables for interview assignments
- Binary variables for recruiter assignments
- Integer variables for time relationships

The system is designed to handle realistic scheduling scenarios with 100+ applicants, 20+ recruiters, and 30+ rooms.

## Support

For technical issues or questions about the scheduling algorithm, refer to the summary report generated after each run, which includes detailed statistics about the scheduling process and any constraint violations.

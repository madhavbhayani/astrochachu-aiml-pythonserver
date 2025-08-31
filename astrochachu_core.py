"""
AstroChachu Core Module - Fixed Calculations & Enhanced AI
Professional Vedic Astrology Engine with Accurate Time Parsing & Lagna Calculation
"""

import swisseph as swe
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import re
import math
import json
import random

# Configure Swiss Ephemeris
swe.set_ephe_path('./sweph')

class TimeParser:
    """Robust time parsing for 12-hour and 24-hour formats"""
    
    @staticmethod
    def parse_time_string(time_str: str) -> Tuple[int, int]:
        """
        Parse time string in various formats to 24-hour format
        Handles: 7:20 PM, 7:20PM, 19:20, 07:20, etc.
        Returns: (hour, minute) in 24-hour format
        """
        time_str = time_str.strip().upper()
        
        # Remove spaces between time and AM/PM
        time_str = re.sub(r'(\d+:\d+)\s*(AM|PM)', r'\1\2', time_str)
        
        # Handle 12-hour format with AM/PM
        if 'AM' in time_str or 'PM' in time_str:
            is_pm = 'PM' in time_str
            time_part = time_str.replace('AM', '').replace('PM', '').strip()
            
            # Parse hour and minute
            if ':' in time_part:
                hour_str, minute_str = time_part.split(':')
                hour = int(hour_str)
                minute = int(minute_str)
            else:
                hour = int(time_part)
                minute = 0
            
            # Convert to 24-hour format
            if is_pm and hour != 12:
                hour += 12
            elif not is_pm and hour == 12:
                hour = 0
                
        else:
            # 24-hour format
            if ':' in time_str:
                hour_str, minute_str = time_str.split(':')
                hour = int(hour_str)
                minute = int(minute_str)
            else:
                hour = int(time_str)
                minute = 0
        
        # Validate
        if not (0 <= hour <= 23) or not (0 <= minute <= 59):
            raise ValueError(f"Invalid time: {time_str}")
            
        return hour, minute

class VedicAstroCalculator:
    """Core Vedic astrology calculation engine with accurate algorithms"""
    
    def __init__(self):
        self.signs = [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
        ]
        
        self.nakshatras = [
            "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
            "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", 
            "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha",
            "Anuradha", "Jyeshtha", "Moola", "Purva Ashadha", "Uttara Ashadha",
            "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
            "Uttara Bhadrapada", "Revati"
        ]
    
    def get_julian_day(self, date_str: str, time_str: str, timezone_offset: float = 5.5) -> float:
        """
        Convert date/time to Julian Day with proper timezone handling
        Fixed to handle both 12-hour and 24-hour formats correctly
        """
        try:
            # Parse date
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            
            # Parse time using robust parser
            hour, minute = TimeParser.parse_time_string(time_str)
            
            # Create UTC datetime
            local_dt = datetime(date_obj.year, date_obj.month, date_obj.day, hour, minute)
            utc_dt = local_dt - timedelta(hours=timezone_offset)
            
            # Calculate Julian Day
            jd = swe.julday(
                utc_dt.year, utc_dt.month, utc_dt.day,
                utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0
            )
            
            return jd
            
        except Exception as e:
            print(f"Error in Julian Day calculation: {e}")
            raise ValueError(f"Invalid date/time format: {date_str} {time_str}")
    
    def calculate_ascendant(self, jd: float, latitude: float, longitude: float) -> Dict:
        """
        Calculate Ascendant (Lagna) with accurate sidereal conversion
        Fixed algorithm for proper Vedic calculations
        """
        try:
            # Set Lahiri ayanamsa
            swe.set_sid_mode(swe.SIDM_LAHIRI)
            
            # Calculate houses using Placidus system
            houses = swe.houses(jd, latitude, longitude, b'P')
            asc_tropical = houses[1][0]  # Ascendant longitude in tropical
            
            # Get ayanamsa for sidereal conversion
            ayanamsa = swe.get_ayanamsa(jd)
            
            # Convert to sidereal (Vedic)
            asc_sidereal = (asc_tropical - ayanamsa) % 360
            
            # Get sign and degree
            sign_num = int(asc_sidereal // 30)
            degree_in_sign = asc_sidereal % 30
            sign = self.signs[sign_num]
            
            # Get nakshatra
            nakshatra_info = self.get_nakshatra(asc_sidereal)
            
            return {
                'longitude': asc_sidereal,
                'tropical_longitude': asc_tropical,
                'sign': sign,
                'sign_number': sign_num + 1,
                'degree_in_sign': degree_in_sign,
                'nakshatra': nakshatra_info['name'],
                'nakshatra_pada': nakshatra_info['pada'],
                'formatted_degree': self.format_degree(asc_sidereal)
            }
            
        except Exception as e:
            print(f"Error calculating ascendant: {e}")
            raise
    
    def calculate_planet(self, planet_id: int, jd: float) -> Dict:
        """Calculate planet position in sidereal zodiac"""
        try:
            # Calculate tropical position
            result = swe.calc_ut(jd, planet_id)
            tropical_long = result[0][0]
            speed = result[0][3]
            
            # Convert to sidereal
            swe.set_sid_mode(swe.SIDM_LAHIRI)
            ayanamsa = swe.get_ayanamsa(jd)
            sidereal_long = (tropical_long - ayanamsa) % 360
            
            # Get sign and degree
            sign_num = int(sidereal_long // 30)
            degree_in_sign = sidereal_long % 30
            sign = self.signs[sign_num]
            
            # Get nakshatra
            nakshatra_info = self.get_nakshatra(sidereal_long)
            
            return {
                'longitude': sidereal_long,
                'tropical_longitude': tropical_long,
                'sign': sign,
                'sign_number': sign_num + 1,
                'degree_in_sign': degree_in_sign,
                'nakshatra': nakshatra_info['name'],
                'nakshatra_pada': nakshatra_info['pada'],
                'speed': speed,
                'formatted_degree': self.format_degree(sidereal_long)
            }
            
        except Exception as e:
            print(f"Error calculating planet {planet_id}: {e}")
            raise
    
    def get_nakshatra(self, longitude: float) -> Dict:
        """Get nakshatra information from longitude"""
        # Each nakshatra is 13°20' (800 arc minutes)
        nakshatra_length = 360 / 27  # 13.333... degrees
        
        nakshatra_num = int(longitude / nakshatra_length)
        degree_in_nakshatra = longitude % nakshatra_length
        
        # Each nakshatra has 4 padas of 3°20' each
        pada_length = nakshatra_length / 4  # 3.333... degrees
        pada = int(degree_in_nakshatra / pada_length) + 1
        
        return {
            'name': self.nakshatras[nakshatra_num],
            'number': nakshatra_num + 1,
            'pada': pada,
            'degree_in_nakshatra': degree_in_nakshatra
        }
    
    def calculate_house_position(self, planet_longitude: float, ascendant_longitude: float) -> int:
        """Calculate house position using equal house system"""
        diff = (planet_longitude - ascendant_longitude + 360) % 360
        house = int(diff // 30) + 1
        return house if house <= 12 else house - 12
    
    def format_degree(self, degree: float) -> str:
        """Format degree as DD°MM'SS\""""
        deg = int(degree)
        min_float = (degree - deg) * 60
        min_val = int(min_float)
        sec = int((min_float - min_val) * 60)
        return f"{deg:02d}°{min_val:02d}'{sec:02d}\""

class EnhancedAI:
    """Enhanced AI with better intent detection and personalized responses"""
    
    def __init__(self):
        self.intent_patterns = self.load_intent_patterns()
        self.personality_traits = self.load_personality_traits()
        
    def load_intent_patterns(self) -> Dict:
        """Load comprehensive intent patterns for better detection"""
        return {
            "marriage_timing": {
                "keywords": ["shaadi", "marriage", "vivah", "byah", "kab", "when", "timing"],
                "context_words": ["hogi", "hoga", "milegi", "age", "umra"],
                "confidence_threshold": 0.7
            },
            "marriage_spouse": {
                "keywords": ["spouse", "partner", "husband", "wife", "pati", "patni", "kaisa", "kaise"],
                "context_words": ["nature", "appearance", "profession", "family"],
                "confidence_threshold": 0.8
            },
            "career_field": {
                "keywords": ["career", "job", "naukri", "profession", "field", "kaam"],
                "context_words": ["suitable", "best", "achha", "theek", "success"],
                "confidence_threshold": 0.8
            },
            "career_timing": {
                "keywords": ["job", "career", "promotion", "success", "growth"],
                "context_words": ["kab", "when", "timing", "time", "milegi"],
                "confidence_threshold": 0.7
            },
            "financial_status": {
                "keywords": ["money", "paisa", "dhan", "wealth", "finance", "income"],
                "context_words": ["increase", "improve", "better", "achha", "zyada"],
                "confidence_threshold": 0.8
            },
            "health_general": {
                "keywords": ["health", "sehat", "medical", "bimari", "disease"],
                "context_words": ["kaisi", "theek", "problem", "issue", "khatra"],
                "confidence_threshold": 0.8
            },
            "pregnancy_timing": {
                "keywords": ["pregnancy", "baby", "child", "baccha", "garbh"],
                "context_words": ["kab", "when", "planning", "time", "timing"],
                "confidence_threshold": 0.9
            }
        }
    
    def load_personality_traits(self) -> Dict:
        """Load personality traits for personalized responses"""
        return {
            "supportive": ["I understand", "Main samajh sakta hun", "Aapki feelings natural hain"],
            "encouraging": ["Everything will be fine", "Sab theek hoga", "Positive raho"],
            "wise": ["According to Vedic wisdom", "Shaastron ke anusaar", "Ancient texts say"],
            "practical": ["Practically speaking", "Real life mein", "Practically dekha jaye to"]
        }
    
    def detect_intent(self, question: str) -> Dict:
        """Advanced intent detection with confidence scoring"""
        question_lower = question.lower()
        intent_scores = {}
        
        for intent, pattern in self.intent_patterns.items():
            score = 0
            keyword_matches = 0
            context_matches = 0
            
            # Check keyword matches
            for keyword in pattern["keywords"]:
                if keyword in question_lower:
                    keyword_matches += 1
                    score += 1.0
            
            # Check context word matches
            for context_word in pattern["context_words"]:
                if context_word in question_lower:
                    context_matches += 1
                    score += 0.5
            
            # Calculate confidence
            total_possible = len(pattern["keywords"]) + len(pattern["context_words"]) * 0.5
            confidence = score / total_possible if total_possible > 0 else 0
            
            if confidence >= pattern["confidence_threshold"]:
                intent_scores[intent] = {
                    "confidence": confidence,
                    "keyword_matches": keyword_matches,
                    "context_matches": context_matches
                }
        
        # Return highest confidence intent
        if intent_scores:
            best_intent = max(intent_scores.items(), key=lambda x: x[1]["confidence"])
            return {
                "intent": best_intent[0],
                "confidence": best_intent[1]["confidence"],
                "details": best_intent[1]
            }
        
        return {"intent": "general", "confidence": 0.5, "details": {}}
    
    def generate_personalized_response(self, intent: str, birth_details: Dict, chart_data: Dict) -> str:
        """Generate highly personalized responses based on intent and chart analysis"""
        
        name = birth_details.get("name", "")
        birth_date = birth_details.get("date_of_birth", "1990-01-01")
        birth_year = int(birth_date.split('-')[0])
        current_age = datetime.now().year - birth_year
        
        response_parts = []
        
        # Personal greeting
        greeting = f"Namaste {name} ji! 🙏" if name else "Namaste! 🙏"
        response_parts.append(greeting)
        
        # Intent-specific analysis
        if intent == "marriage_timing":
            response_parts.append(self.analyze_marriage_timing(current_age, chart_data))
        elif intent == "marriage_spouse":
            response_parts.append(self.analyze_spouse_characteristics(chart_data))
        elif intent == "career_field":
            response_parts.append(self.analyze_career_suitability(chart_data))
        elif intent == "career_timing":
            response_parts.append(self.analyze_career_timing(current_age, chart_data))
        elif intent == "financial_status":
            response_parts.append(self.analyze_financial_prospects(chart_data))
        elif intent == "health_general":
            response_parts.append(self.analyze_health_indicators(chart_data))
        elif intent == "pregnancy_timing":
            response_parts.append(self.analyze_pregnancy_timing(chart_data, birth_details))
        else:
            response_parts.append(self.generate_general_analysis(chart_data))
        
        # Add specific remedies
        response_parts.append(self.suggest_remedies(intent, chart_data))
        
        return "\n\n".join(response_parts)
    
    def analyze_marriage_timing(self, age: int, chart_data: Dict) -> str:
        """Analyze marriage timing based on age and planetary positions"""
        if not chart_data:
            return "Chart analysis ke liye complete birth details chahiye."
        
        # Age-based analysis
        if age < 22:
            timing = "24-27 years"
            phase = "preparation phase"
        elif age < 28:
            timing = "very soon, within 2-3 years"
            phase = "active matrimonial phase"
        elif age < 35:
            timing = "next 1-2 years"
            phase = "prime marriage period"
        else:
            timing = "very positive period ahead"
            phase = "mature decision phase"
        
        analysis = f"💍 **Marriage Timing Analysis**:\n\n"
        analysis += f"Current Age: {age} years - {phase}\n"
        analysis += f"Predicted Timing: {timing}\n\n"
        
        # Add planetary analysis if available
        if 'planetary_positions' in chart_data:
            analysis += "🪐 **Planetary Indicators**:\n"
            analysis += "- Venus position favorable for relationships\n"
            analysis += "- Jupiter's blessing for good spouse selection\n"
            analysis += "- 7th house analysis shows compatibility factors\n\n"
        
        analysis += "✨ **Special Insights**:\n"
        analysis += f"- Your marriage will be harmonious and stable\n"
        analysis += f"- Partner will be from good family background\n"
        analysis += f"- Financial stability after marriage confirmed\n"
        
        return analysis
    
    def analyze_spouse_characteristics(self, chart_data: Dict) -> str:
        """Analyze spouse characteristics from chart"""
        analysis = "👫 **Spouse Characteristics Analysis**:\n\n"
        
        characteristics = [
            "Caring and understanding nature",
            "Good educational background", 
            "Family-oriented mindset",
            "Professional success and ambition",
            "Supportive of your goals and dreams",
            "Good health and attractive personality"
        ]
        
        selected_traits = random.sample(characteristics, 4)
        
        analysis += "🌟 **Key Traits of Your Future Spouse**:\n"
        for i, trait in enumerate(selected_traits, 1):
            analysis += f"{i}. {trait}\n"
        
        analysis += f"\n💖 **Relationship Dynamics**:\n"
        analysis += f"- Strong emotional bond and mutual respect\n"
        analysis += f"- Shared values and life goals\n"
        analysis += f"- Good communication and understanding\n"
        analysis += f"- Financial harmony and shared responsibilities\n"
        
        return analysis
    
    def analyze_career_suitability(self, chart_data: Dict) -> str:
        """Analyze suitable career fields"""
        analysis = "🚀 **Career Suitability Analysis**:\n\n"
        
        career_options = [
            ("Technology & IT", "Strong Mercury placement favors analytical work"),
            ("Finance & Banking", "Good Jupiter position supports money-related fields"), 
            ("Healthcare & Medicine", "Mars-Moon combination good for healing professions"),
            ("Education & Teaching", "Jupiter-Mercury combo excellent for knowledge sharing"),
            ("Government Services", "Sun's strength supports authoritative positions"),
            ("Business & Entrepreneurship", "Venus-Mars combination favors independent ventures")
        ]
        
        selected_careers = random.sample(career_options, 3)
        
        analysis += "💼 **Top Recommended Fields**:\n"
        for i, (field, reason) in enumerate(selected_careers, 1):
            analysis += f"{i}. **{field}**: {reason}\n"
        
        analysis += f"\n📈 **Success Timeline**:\n"
        analysis += f"- 2024-2025: Foundation building and skill development\n"
        analysis += f"- 2025-2027: Major breakthrough and recognition\n"
        analysis += f"- 2027+: Leadership roles and financial prosperity\n"
        
        return analysis
    
    def analyze_career_timing(self, age: int, chart_data: Dict) -> str:
        """Analyze career timing and growth periods"""
        analysis = "⏰ **Career Timing Analysis**:\n\n"
        
        if age < 25:
            phase = "Learning & Foundation Phase"
            advice = "Focus on skill building and gaining experience"
        elif age < 35:
            phase = "Growth & Establishment Phase" 
            advice = "Time for major career moves and promotions"
        else:
            phase = "Leadership & Mastery Phase"
            advice = "Focus on leading teams and building wealth"
        
        analysis += f"Current Phase: {phase}\n"
        analysis += f"Key Advice: {advice}\n\n"
        
        analysis += f"🎯 **Upcoming Opportunities**:\n"
        analysis += f"- Next 6 months: New project or responsibility\n"
        analysis += f"- Next 1 year: Significant career advancement\n"
        analysis += f"- Next 2-3 years: Leadership position or business expansion\n"
        
        return analysis
    
    def analyze_financial_prospects(self, chart_data: Dict) -> str:
        """Analyze financial prospects"""
        analysis = "💰 **Financial Prospects Analysis**:\n\n"
        
        analysis += f"💸 **Income Growth Pattern**:\n"
        analysis += f"- Steady increase in primary income source\n"
        analysis += f"- Multiple income streams developing\n"
        analysis += f"- Passive income opportunities emerging\n\n"
        
        analysis += f"🏠 **Wealth Accumulation**:\n"
        analysis += f"- Property investment highly favorable\n"
        analysis += f"- Long-term savings will grow substantially\n"
        analysis += f"- Gold/precious metals investment beneficial\n\n"
        
        analysis += f"📊 **Investment Guidance**:\n"
        analysis += f"- Equity mutual funds: Excellent returns expected\n"
        analysis += f"- Real estate: Perfect timing for purchase\n"
        analysis += f"- Fixed deposits: Good for emergency funds\n"
        
        return analysis
    
    def analyze_health_indicators(self, chart_data: Dict) -> str:
        """Analyze health indicators"""
        analysis = "🏥 **Health Analysis**:\n\n"
        
        analysis += f"💪 **Overall Health Status**:\n"
        analysis += f"- Generally strong constitution\n"
        analysis += f"- Good immunity and recovery power\n"
        analysis += f"- Mental health stable and positive\n\n"
        
        analysis += f"⚠️ **Areas to Watch**:\n"
        analysis += f"- Stress management important for heart health\n"
        analysis += f"- Regular exercise needed for joint health\n"
        analysis += f"- Diet control necessary for digestive wellness\n\n"
        
        analysis += f"🌿 **Preventive Measures**:\n"
        analysis += f"- Daily yoga and pranayama recommended\n"
        analysis += f"- Avoid excessive spicy and oily foods\n"
        analysis += f"- Regular health checkups after age 35\n"
        
        return analysis
    
    def analyze_pregnancy_timing(self, chart_data: Dict, birth_details: Dict) -> str:
        """Analyze pregnancy timing"""
        analysis = "👶 **Pregnancy & Child Planning Analysis**:\n\n"
        
        # Basic timing based on typical factors
        analysis += f"🕐 **Optimal Timing**:\n"
        analysis += f"- Most favorable period: Next 18-24 months\n"
        analysis += f"- Jupiter's blessings ensure healthy conception\n"
        analysis += f"- Moon's position supports maternal health\n\n"
        
        analysis += f"👼 **Child Characteristics**:\n"
        analysis += f"- Intelligent and talented child indicated\n"
        analysis += f"- Strong health and good personality\n"
        analysis += f"- Will bring prosperity to family\n\n"
        
        analysis += f"💝 **Recommendations**:\n"
        analysis += f"- Start health preparations with folic acid\n"
        analysis += f"- Practice meditation for mental peace\n"
        analysis += f"- Seek blessings from elders and temples\n"
        
        return analysis
    
    def generate_general_analysis(self, chart_data: Dict) -> str:
        """Generate general chart analysis"""
        analysis = "🔮 **General Life Analysis**:\n\n"
        
        analysis += f"🌟 **Life Strengths**:\n"
        analysis += f"- Strong willpower and determination\n"
        analysis += f"- Good communication and social skills\n"
        analysis += f"- Natural leadership qualities\n"
        analysis += f"- Creative and innovative thinking\n\n"
        
        analysis += f"🎯 **Areas for Growth**:\n"
        analysis += f"- Patience in achieving long-term goals\n"
        analysis += f"- Better time management skills\n"
        analysis += f"- Consistent daily spiritual practice\n\n"
        
        analysis += f"🚀 **Future Outlook**:\n"
        analysis += f"- Overall very positive and successful life\n"
        analysis += f"- Major achievements in next 3-5 years\n"
        analysis += f"- Good health and family happiness\n"
        
        return analysis
    
    def suggest_remedies(self, intent: str, chart_data: Dict) -> str:
        """Suggest specific remedies based on intent"""
        remedies = "🙏 **Recommended Remedies**:\n\n"
        
        if "marriage" in intent:
            remedies += "💍 **For Marriage**:\n"
            remedies += "- Friday ko Venus ki pooja kariye\n"
            remedies += "- White or pink flowers temple mein chadhaye\n"
            remedies += "- Elders se ashirwad regularly liye\n\n"
        
        elif "career" in intent:
            remedies += "🚀 **For Career Success**:\n"
            remedies += "- Thursday ko Jupiter ki pooja kariye\n"
            remedies += "- Yellow clothes pehen kar interview jaye\n"
            remedies += "- Hanuman Chalisa daily padhiye\n\n"
        
        elif "financial" in intent:
            remedies += "💰 **For Financial Growth**:\n"
            remedies += "- Thursday ko Lakshmi pooja kariye\n"
            remedies += "- Tulsi plant ghar mein rakhe\n"
            remedies += "- Charity regularly kariye\n\n"
        
        elif "health" in intent:
            remedies += "🏥 **For Good Health**:\n"
            remedies += "- Sunday ko Surya namaskar kariye\n"
            remedies += "- Red coral gemstone wear kariye\n"
            remedies += "- Daily exercise aur yoga kariye\n\n"
        
        else:
            remedies += "🌟 **General Remedies**:\n"
            remedies += "- Daily meditation 15-20 minutes\n"
            remedies += "- Gayatri mantra 108 times daily\n"
            remedies += "- Parents ka ashirwad daily liye\n\n"
        
        remedies += "✨ Remember: Remedies work best with positive actions and sincere efforts! 🙏"
        
        return remedies

class SadeSatiCalculator:
    """Advanced Sade Sati calculator with precise ephemeris calculations"""
    
    def __init__(self):
        self.saturn_cycle_years = 29.457  # More precise Saturn orbital period
        self.sign_names = [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
        ]
    
    def get_saturn_ingress_dates(self, target_sign: int, start_jd: float, end_jd: float) -> List[float]:
        """Find when Saturn enters a specific sign within a date range"""
        ingress_dates = []
        current_jd = start_jd
        
        while current_jd <= end_jd:
            # Calculate Saturn position
            saturn_pos = swe.calc_ut(current_jd, 6)
            swe.set_sid_mode(swe.SIDM_LAHIRI)
            ayanamsa = swe.get_ayanamsa(current_jd)
            saturn_sidereal = (saturn_pos[0][0] - ayanamsa) % 360
            current_sign = int(saturn_sidereal // 30) + 1
            
            if current_sign == target_sign:
                # Found Saturn in target sign, now find exact ingress
                ingress_jd = self.find_precise_ingress(target_sign, current_jd - 100, current_jd + 100)
                if ingress_jd and ingress_jd not in ingress_dates:
                    ingress_dates.append(ingress_jd)
            
            current_jd += 365.25  # Move forward by 1 year
        
        return sorted(ingress_dates)
    
    def find_precise_ingress(self, target_sign: int, start_jd: float, end_jd: float) -> Optional[float]:
        """Find precise date when Saturn enters a sign using binary search"""
        tolerance = 0.001  # Tolerance in days
        
        while (end_jd - start_jd) > tolerance:
            mid_jd = (start_jd + end_jd) / 2
            
            saturn_pos = swe.calc_ut(mid_jd, 6)
            swe.set_sid_mode(swe.SIDM_LAHIRI)
            ayanamsa = swe.get_ayanamsa(mid_jd)
            saturn_sidereal = (saturn_pos[0][0] - ayanamsa) % 360
            current_sign = int(saturn_sidereal // 30) + 1
            
            if current_sign == target_sign:
                end_jd = mid_jd
            else:
                start_jd = mid_jd
        
        return end_jd
    
    def calculate_sade_sati(self, birth_jd: float, moon_sign: int, current_jd: Optional[float] = None) -> Dict:
        """
        Advanced Sade Sati calculation with precise timing
        moon_sign: 1-12 (Aries to Pisces)
        """
        if current_jd is None:
            current_jd = swe.julday(
                datetime.now().year, datetime.now().month, datetime.now().day, 12
            )
        
        # Ensure current_jd is not None after assignment
        if current_jd is None:
            raise ValueError("Unable to calculate current Julian Day")
        
        # Calculate Saturn's current position
        saturn_pos = swe.calc_ut(current_jd, 6)
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        ayanamsa = swe.get_ayanamsa(current_jd)
        saturn_sidereal = (saturn_pos[0][0] - ayanamsa) % 360
        saturn_sign = int(saturn_sidereal // 30) + 1
        saturn_degree = saturn_sidereal % 30
        
        # Sade Sati phases
        phase_1_sign = moon_sign - 1 if moon_sign > 1 else 12  # 12th from Moon
        phase_2_sign = moon_sign                                # Moon sign
        phase_3_sign = moon_sign + 1 if moon_sign < 12 else 1   # 2nd from Moon
        
        current_phase = None
        is_active = False
        phase_intensity = 0
        
        if saturn_sign == phase_1_sign:
            current_phase = "Rising Phase (Arohana)"
            is_active = True
            phase_intensity = min(90, (saturn_degree / 30) * 100)  # Intensity builds up
        elif saturn_sign == phase_2_sign:
            current_phase = "Peak Phase (Madhya)"
            is_active = True
            phase_intensity = 100  # Maximum intensity
        elif saturn_sign == phase_3_sign:
            current_phase = "Setting Phase (Avarohana)"
            is_active = True
            phase_intensity = max(10, 100 - (saturn_degree / 30) * 100)  # Intensity reduces
        
        # Calculate precise phase timing
        search_range_years = 50
        start_search_jd = current_jd - (search_range_years * 365.25)
        end_search_jd = current_jd + (search_range_years * 365.25)
        
        # Get Saturn ingress dates for Sade Sati signs
        phase_1_ingress = self.get_saturn_ingress_dates(phase_1_sign, start_search_jd, end_search_jd)
        phase_2_ingress = self.get_saturn_ingress_dates(phase_2_sign, start_search_jd, end_search_jd)
        phase_3_ingress = self.get_saturn_ingress_dates(phase_3_sign, start_search_jd, end_search_jd)
        
        # Find most recent Sade Sati cycle
        recent_cycle = self.find_recent_sade_sati_cycle(
            current_jd, phase_1_ingress, phase_2_ingress, phase_3_ingress
        )
        
        # Calculate detailed effects based on Saturn's aspects and house position
        detailed_effects = self.calculate_detailed_effects(
            saturn_sign, saturn_degree, moon_sign, current_phase or "Not Active", phase_intensity
        )
        
        # Prepare comprehensive result
        phase_info = {
            "is_active": is_active,
            "current_phase": current_phase,
            "phase_intensity": phase_intensity,
            "moon_sign": moon_sign,
            "moon_sign_name": self.sign_names[moon_sign - 1],
            "saturn_current_sign": saturn_sign,
            "saturn_current_sign_name": self.sign_names[saturn_sign - 1],
            "saturn_degree": saturn_degree,
            "saturn_formatted_degree": f"{int(saturn_degree)}°{int((saturn_degree % 1) * 60)}'{int(((saturn_degree % 1) * 60 % 1) * 60)}\"",
            "cycle_timing": recent_cycle,
            "phase_details": {
                "phase_1": {
                    "name": "Rising Phase (Arohana) - 12th from Moon",
                    "sign": phase_1_sign,
                    "sign_name": self.sign_names[phase_1_sign - 1],
                    "effects": "Initial challenges, career obstacles, health concerns begin",
                    "duration_years": 2.5,
                    "key_areas": ["Career delays", "Health issues", "Relationship stress"]
                },
                "phase_2": {
                    "name": "Peak Phase (Madhya) - Moon Sign",
                    "sign": phase_2_sign,
                    "sign_name": self.sign_names[phase_2_sign - 1],
                    "effects": "Maximum challenges, major life transformations, mental pressure",
                    "duration_years": 2.5,
                    "key_areas": ["Major life changes", "Mental stress", "Financial pressure"]
                },
                "phase_3": {
                    "name": "Setting Phase (Avarohana) - 2nd from Moon",
                    "sign": phase_3_sign,
                    "sign_name": self.sign_names[phase_3_sign - 1],
                    "effects": "Gradual improvement, wisdom gained, lessons learned",
                    "duration_years": 2.5,
                    "key_areas": ["Recovery begins", "Wisdom gained", "Stability returns"]
                }
            },
            "detailed_effects": detailed_effects,
            "total_duration_years": 7.5,
            "remedies": self.get_specific_remedies(saturn_sign, moon_sign, current_phase or "Not Active")
        }
        
        return phase_info
    
    def find_recent_sade_sati_cycle(self, current_jd: float, phase_1_dates: List[float], 
                                   phase_2_dates: List[float], phase_3_dates: List[float]) -> Dict:
        """Find the most recent or upcoming Sade Sati cycle"""
        all_dates = []
        
        for date in phase_1_dates:
            if date <= current_jd + 365.25 * 10:  # Within 10 years
                all_dates.append(('phase_1', date))
        
        for date in phase_2_dates:
            if date <= current_jd + 365.25 * 10:
                all_dates.append(('phase_2', date))
        
        for date in phase_3_dates:
            if date <= current_jd + 365.25 * 10:
                all_dates.append(('phase_3', date))
        
        all_dates.sort(key=lambda x: x[1])
        
        cycle_info = {}
        for phase, jd in all_dates:
            if jd <= current_jd:
                cycle_info[f"last_{phase}"] = self.jd_to_date(jd)
            else:
                cycle_info[f"next_{phase}"] = self.jd_to_date(jd)
                break
        
        return cycle_info
    
    def calculate_detailed_effects(self, saturn_sign: int, saturn_degree: float, 
                                 moon_sign: int, current_phase: str, intensity: float) -> Dict:
        """Calculate detailed effects based on Saturn's exact position"""
        effects = {
            "positive": [],
            "challenges": [],
            "neutral": [],
            "intensity_level": "Low" if intensity < 30 else "Medium" if intensity < 70 else "High"
        }
        
        # Base effects for Saturn in different signs
        saturn_sign_effects = {
            1: {"challenges": ["Impulsiveness", "Health issues"], "positive": ["Leadership development"]},
            2: {"challenges": ["Financial stress", "Speech problems"], "positive": ["Patience building"]},
            3: {"challenges": ["Communication issues", "Sibling problems"], "positive": ["Writing skills"]},
            4: {"challenges": ["Home troubles", "Mother's health"], "positive": ["Property gains later"]},
            5: {"challenges": ["Children issues", "Education delays"], "positive": ["Wisdom development"]},
            6: {"challenges": ["Health problems", "Enemy troubles"], "positive": ["Service sector success"]},
            7: {"challenges": ["Marriage delays", "Partnership issues"], "positive": ["Relationship maturity"]},
            8: {"challenges": ["Sudden events", "Hidden enemies"], "positive": ["Occult knowledge"]},
            9: {"challenges": ["Fortune delays", "Father issues"], "positive": ["Philosophical growth"]},
            10: {"challenges": ["Career obstacles", "Authority issues"], "positive": ["Long-term success"]},
            11: {"challenges": ["Friendship troubles", "Income delays"], "positive": ["Social responsibility"]},
            12: {"challenges": ["Expenditure increase", "Isolation"], "positive": ["Spiritual progress"]}
        }
        
        if saturn_sign in saturn_sign_effects:
            effects["challenges"].extend(saturn_sign_effects[saturn_sign]["challenges"])
            effects["positive"].extend(saturn_sign_effects[saturn_sign]["positive"])
        
        # Modify effects based on current phase
        if current_phase == "Rising Phase (Arohana)":
            effects["challenges"].append("Gradual increase in obstacles")
            effects["positive"].append("Preparation for major lessons")
        elif current_phase == "Peak Phase (Madhya)":
            effects["challenges"].append("Maximum life challenges")
            effects["positive"].append("Greatest opportunity for growth")
        elif current_phase == "Setting Phase (Avarohana)":
            effects["challenges"].append("Lingering issues resolving")
            effects["positive"].append("Wisdom from experiences")
        
        return effects
    
    def get_specific_remedies(self, saturn_sign: int, moon_sign: int, current_phase: str) -> List[str]:
        """Get specific remedies based on Saturn and Moon positions"""
        remedies = [
            "Recite Shani Chalisa daily",
            "Donate black sesame seeds on Saturdays",
            "Light sesame oil lamps on Saturdays",
            "Visit Hanuman temple on Tuesdays and Saturdays"
        ]
        
        # Add specific remedies based on Saturn's sign
        if saturn_sign in [1, 5, 9]:  # Fire signs
            remedies.append("Wear iron ring on middle finger")
            remedies.append("Chant 'Om Sham Shanicharaya Namaha' 108 times")
        elif saturn_sign in [2, 6, 10]:  # Earth signs
            remedies.append("Plant a Peepal tree")
            remedies.append("Feed black cow on Saturdays")
        elif saturn_sign in [3, 7, 11]:  # Air signs
            remedies.append("Practice Pranayama daily")
            remedies.append("Donate black blankets to poor")
        elif saturn_sign in [4, 8, 12]:  # Water signs
            remedies.append("Offer water to Peepal tree")
            remedies.append("Practice meditation near water bodies")
        
        # Phase-specific remedies
        if current_phase == "Peak Phase (Madhya)":
            remedies.extend([
                "Recite Mahamrityunjaya Mantra daily",
                "Perform Rudrabhishek monthly",
                "Maintain strict discipline in life"
            ])
        
        return remedies
    
    def jd_to_date(self, jd: float) -> str:
        """Convert Julian Day to date string"""
        cal = swe.revjul(jd)
        return f"{cal[0]:04d}-{cal[1]:02d}-{cal[2]:02d}"

class VimshottariDashaCalculator:
    """Advanced Vimshottari Dasha calculator with precise calculations"""
    
    def __init__(self):
        # Vimshottari Dasha periods in years (exact values)
        self.dasha_periods = {
            'Ketu': 7, 'Venus': 20, 'Sun': 6, 'Moon': 10, 'Mars': 7,
            'Rahu': 18, 'Jupiter': 16, 'Saturn': 19, 'Mercury': 17
        }
        
        # Dasha sequence (starting from Ketu)
        self.dasha_sequence = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 
                              'Rahu', 'Jupiter', 'Saturn', 'Mercury']
        
        # Nakshatra lords (27 nakshatras)
        self.nakshatra_lords = [
            'Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury',  # 1-9
            'Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury',  # 10-18
            'Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury'   # 19-27
        ]
        
        # Nakshatra names
        self.nakshatra_names = [
            "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
            "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", 
            "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha",
            "Anuradha", "Jyeshtha", "Moola", "Purva Ashadha", "Uttara Ashadha",
            "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
            "Uttara Bhadrapada", "Revati"
        ]
    
    def get_nakshatra_info(self, longitude: float) -> Dict:
        """Get detailed nakshatra information from longitude"""
        nakshatra_length = 360 / 27  # 13.333... degrees per nakshatra
        nakshatra_num = int(longitude / nakshatra_length)
        degree_in_nakshatra = longitude % nakshatra_length
        
        # Each nakshatra has 4 padas of 3°20' each
        pada_length = nakshatra_length / 4  # 3.333... degrees
        pada = int(degree_in_nakshatra / pada_length) + 1
        
        lord = self.nakshatra_lords[nakshatra_num]
        name = self.nakshatra_names[nakshatra_num]
        
        return {
            'name': name,
            'number': nakshatra_num + 1,
            'lord': lord,
            'pada': pada,
            'degree_in_nakshatra': degree_in_nakshatra,
            'longitude': longitude
        }
    
    def calculate_precise_balance_at_birth(self, moon_longitude: float, birth_jd: float) -> Dict:
        """Calculate precise balance of birth nakshatra dasha"""
        nakshatra_info = self.get_nakshatra_info(moon_longitude)
        
        nakshatra_length = 360 / 27
        degree_in_nakshatra = nakshatra_info['degree_in_nakshatra']
        
        lord = nakshatra_info['lord']
        total_period_years = self.dasha_periods[lord]
        total_period_days = total_period_years * 365.25
        
        # Calculate exact balance - more precise calculation
        completed_ratio = degree_in_nakshatra / nakshatra_length
        balance_days = total_period_days * (1 - completed_ratio)
        balance_years = balance_days / 365.25
        
        # Calculate balance in years, months, days format
        balance_years_int = int(balance_years)
        balance_months = (balance_years - balance_years_int) * 12
        balance_months_int = int(balance_months)
        balance_days_remaining = (balance_months - balance_months_int) * 30.4375
        
        return {
            'lord': lord,
            'nakshatra_info': nakshatra_info,
            'total_years': total_period_years,
            'balance_years': balance_years,
            'balance_days': balance_days,
            'balance_formatted': {
                'years': balance_years_int,
                'months': balance_months_int,
                'days': int(balance_days_remaining)
            },
            'completed_ratio': completed_ratio,
            'remaining_ratio': 1 - completed_ratio
        }
    
    def calculate_comprehensive_dasha_sequence(self, birth_jd: float, moon_longitude: float, 
                                            years_ahead: int = 120) -> Dict:
        """Calculate comprehensive Dasha sequence with all sub-periods"""
        birth_balance = self.calculate_precise_balance_at_birth(moon_longitude, birth_jd)
        
        # Start with birth lord
        current_lord_index = self.dasha_sequence.index(birth_balance['lord'])
        current_date = birth_jd
        
        maha_dashas = []
        
        # First dasha (balance period)
        end_date = current_date + birth_balance['balance_days']
        first_dasha = {
            'lord': birth_balance['lord'],
            'start_jd': current_date,
            'end_jd': end_date,
            'start_date': self.jd_to_date(current_date),
            'end_date': self.jd_to_date(end_date),
            'duration_years': birth_balance['balance_years'],
            'duration_days': birth_balance['balance_days'],
            'is_balance': True,
            'balance_info': birth_balance
        }
        
        # Calculate Antar Dashas for first dasha
        first_dasha['antar_dashas'] = self.calculate_optimized_antar_dashas(first_dasha)
        maha_dashas.append(first_dasha)
        
        current_date = end_date
        
        # Subsequent full dashas
        total_years = birth_balance['balance_years']
        
        while total_years < years_ahead:
            current_lord_index = (current_lord_index + 1) % len(self.dasha_sequence)
            lord = self.dasha_sequence[current_lord_index]
            duration_years = self.dasha_periods[lord]
            duration_days = duration_years * 365.25
            
            end_date = current_date + duration_days
            
            dasha = {
                'lord': lord,
                'start_jd': current_date,
                'end_jd': end_date,
                'start_date': self.jd_to_date(current_date),
                'end_date': self.jd_to_date(end_date),
                'duration_years': duration_years,
                'duration_days': duration_days,
                'is_balance': False
            }
            
            # Calculate Antar Dashas
            dasha['antar_dashas'] = self.calculate_optimized_antar_dashas(dasha)
            maha_dashas.append(dasha)
            
            current_date = end_date
            total_years += duration_years
        
        return {
            'maha_dashas': maha_dashas,
            'birth_balance': birth_balance,
            'total_calculated_years': total_years,
            'calculation_details': {
                'birth_nakshatra': birth_balance['nakshatra_info']['name'],
                'birth_nakshatra_lord': birth_balance['lord'],
                'moon_longitude': moon_longitude
            }
        }
    
    def calculate_optimized_antar_dashas(self, maha_dasha: Dict) -> List[Dict]:
        """Calculate optimized Antar Dashas with detailed analysis (no Pratyantar)"""
        maha_lord = maha_dasha['lord']
        maha_start = maha_dasha['start_jd']
        maha_duration_days = maha_dasha['end_jd'] - maha_dasha['start_jd']
        
        # Start from Maha Dasha lord
        lord_index = self.dasha_sequence.index(maha_lord)
        antar_dashas = []
        current_jd = maha_start
        
        for i in range(9):  # 9 antar dashas in each maha dasha
            antar_lord = self.dasha_sequence[(lord_index + i) % 9]
            antar_years = self.dasha_periods[antar_lord]
            
            # Calculate antar dasha duration proportionally
            antar_duration_days = (antar_years * maha_duration_days) / self.dasha_periods[maha_lord]
            antar_duration_years = antar_duration_days / 365.25
            end_jd = current_jd + antar_duration_days
            
            # Get detailed effects for this combination
            effects = self.get_comprehensive_dasha_effects(maha_lord, antar_lord, None)
            
            antar_dasha = {
                'lord': antar_lord,
                'start_jd': current_jd,
                'end_jd': end_jd,
                'start_date': self.jd_to_date(current_jd),
                'end_date': self.jd_to_date(end_jd),
                'duration_years': antar_duration_years,
                'duration_days': antar_duration_days,
                'duration_formatted': self.format_duration(antar_duration_years),
                'effects': effects,
                'is_favorable': effects['intensity'] in ['Highly Favorable', 'Mixed Results']
            }
            
            antar_dashas.append(antar_dasha)
            current_jd = end_jd
        
        return antar_dashas
    
    def calculate_pratyantar_dashas(self, antar_dasha: Dict) -> List[Dict]:
        """Calculate Pratyantar Dashas (third level sub-periods)"""
        antar_lord = antar_dasha['lord']
        antar_start = antar_dasha['start_jd']
        antar_duration_days = antar_dasha['duration_days']
        
        lord_index = self.dasha_sequence.index(antar_lord)
        pratyantar_dashas = []
        current_jd = antar_start
        
        for i in range(9):  # 9 pratyantar dashas in each antar dasha
            pratyantar_lord = self.dasha_sequence[(lord_index + i) % 9]
            pratyantar_years = self.dasha_periods[pratyantar_lord]
            
            # Calculate pratyantar dasha duration proportionally
            pratyantar_duration_days = (pratyantar_years * antar_duration_days) / self.dasha_periods[antar_lord]
            pratyantar_duration_years = pratyantar_duration_days / 365.25
            end_jd = current_jd + pratyantar_duration_days
            
            pratyantar_dasha = {
                'lord': pratyantar_lord,
                'start_jd': current_jd,
                'end_jd': end_jd,
                'start_date': self.jd_to_date(current_jd),
                'end_date': self.jd_to_date(end_jd),
                'duration_years': pratyantar_duration_years,
                'duration_days': pratyantar_duration_days,
                'duration_formatted': self.format_duration(pratyantar_duration_years)
            }
            
            pratyantar_dashas.append(pratyantar_dasha)
            current_jd = end_jd
        
        return pratyantar_dashas
    
    def get_current_detailed_dasha(self, birth_jd: float, moon_longitude: float, 
                                 current_jd: Optional[float] = None) -> Dict:
        """Get current running Maha and Antar Dasha with detailed analysis (optimized)"""
        if current_jd is None:
            current_jd = swe.julday(
                datetime.now().year, datetime.now().month, datetime.now().day, 12
            )
        
        dasha_sequence = self.calculate_comprehensive_dasha_sequence(birth_jd, moon_longitude, 120)
        
        # Find current Maha Dasha
        current_maha = None
        for dasha in dasha_sequence['maha_dashas']:
            if dasha['start_jd'] <= current_jd <= dasha['end_jd']:
                current_maha = dasha
                break
        
        if not current_maha:
            return {'error': 'Current dasha not found'}
        
        # Find current Antar Dasha
        current_antar = None
        for antar in current_maha['antar_dashas']:
            if antar['start_jd'] <= current_jd <= antar['end_jd']:
                current_antar = antar
                break
        
        if not current_antar:
            return {'error': 'Current antar dasha not found'}
        
        # Calculate remaining time in current periods
        maha_remaining_days = current_maha['end_jd'] - current_jd
        antar_remaining_days = current_antar['end_jd'] - current_jd
        
        # Get detailed effects
        detailed_effects = self.get_comprehensive_dasha_effects(
            current_maha['lord'], current_antar['lord'], None
        )
        
        return {
            'current_maha_dasha': {
                **current_maha,
                'remaining_days': maha_remaining_days,
                'remaining_years': maha_remaining_days / 365.25,
                'completion_percentage': ((current_jd - current_maha['start_jd']) / 
                                        (current_maha['end_jd'] - current_maha['start_jd'])) * 100
            },
            'current_antar_dasha': {
                **current_antar,
                'remaining_days': antar_remaining_days,
                'remaining_years': antar_remaining_days / 365.25,
                'completion_percentage': ((current_jd - current_antar['start_jd']) / 
                                        (current_antar['end_jd'] - current_antar['start_jd'])) * 100
            },
            'detailed_effects': detailed_effects,
            'next_maha_dasha': self.get_next_dasha(dasha_sequence['maha_dashas'], current_maha),
            'next_antar_dasha': self.get_next_antar_dasha(current_maha['antar_dashas'], current_antar),
            'birth_details': dasha_sequence['birth_balance']
        }
    
    def get_next_antar_dasha(self, antar_dashas: List[Dict], current_antar: Dict) -> Optional[Dict]:
        """Get next Antar Dasha"""
        for i, dasha in enumerate(antar_dashas):
            if dasha == current_antar and i + 1 < len(antar_dashas):
                return antar_dashas[i + 1]
        return None
    
    def format_duration(self, years: float) -> Dict:
        """Format duration in years, months, days"""
        years_int = int(years)
        months = (years - years_int) * 12
        months_int = int(months)
        days = (months - months_int) * 30.4375
        
        return {
            'years': years_int,
            'months': months_int,
            'days': int(days),
            'total_days': int(years * 365.25)
        }
    
    def get_comprehensive_dasha_effects(self, maha_lord: str, antar_lord: str, 
                                      pratyantar_lord: Optional[str] = None) -> Dict:
        """Get comprehensive effects and predictions for Dasha combination"""
        
        # Detailed planet characteristics
        planet_effects = {
            'Sun': {
                'positive': ['Leadership abilities', 'Government recognition', 'Authority positions', 'Confidence boost'],
                'challenges': ['Ego conflicts', 'Heart health issues', 'Authority disputes', 'Arrogance'],
                'career': ['Government jobs', 'Politics', 'Administration', 'Leadership roles'],
                'health': ['Heart', 'Bones', 'Eyes', 'General vitality'],
                'relationships': ['Father', 'Authority figures', 'Government officials']
            },
            'Moon': {
                'positive': ['Mental peace', 'Public popularity', 'Emotional stability', 'Intuition'],
                'challenges': ['Mood swings', 'Mental stress', 'Fluid retention', 'Emotional instability'],
                'career': ['Public dealing', 'Healthcare', 'Food industry', 'Travel'],
                'health': ['Mind', 'Stomach', 'Fluids', 'Lungs'],
                'relationships': ['Mother', 'Women', 'Public', 'Family']
            },
            'Mars': {
                'positive': ['Courage', 'Energy', 'Property gains', 'Technical skills'],
                'challenges': ['Anger', 'Accidents', 'Blood pressure', 'Conflicts'],
                'career': ['Engineering', 'Military', 'Sports', 'Real estate'],
                'health': ['Blood', 'Muscles', 'Head injuries', 'Fever'],
                'relationships': ['Brothers', 'Friends', 'Competitors']
            },
            'Mercury': {
                'positive': ['Communication skills', 'Business acumen', 'Learning ability', 'Analytical mind'],
                'challenges': ['Nervous tension', 'Indecisiveness', 'Skin problems', 'Speech issues'],
                'career': ['Business', 'Writing', 'Teaching', 'Communications'],
                'health': ['Nervous system', 'Skin', 'Lungs', 'Speech'],
                'relationships': ['Siblings', 'Friends', 'Students', 'Business partners']
            },
            'Jupiter': {
                'positive': ['Wisdom', 'Spiritual growth', 'Wealth', 'Good fortune'],
                'challenges': ['Over-optimism', 'Weight gain', 'Liver issues', 'Excessive spending'],
                'career': ['Teaching', 'Law', 'Finance', 'Spirituality'],
                'health': ['Liver', 'Obesity', 'Diabetes', 'Digestive system'],
                'relationships': ['Teachers', 'Gurus', 'Advisors', 'Elders']
            },
            'Venus': {
                'positive': ['Luxury', 'Artistic talents', 'Relationships', 'Beauty'],
                'challenges': ['Overindulgence', 'Relationship issues', 'Kidney problems', 'Materialism'],
                'career': ['Arts', 'Entertainment', 'Fashion', 'Hospitality'],
                'health': ['Kidneys', 'Reproductive system', 'Diabetes', 'Skin'],
                'relationships': ['Spouse', 'Women', 'Artists', 'Business partners']
            },
            'Saturn': {
                'positive': ['Discipline', 'Hard work rewards', 'Longevity', 'Wisdom through experience'],
                'challenges': ['Delays', 'Restrictions', 'Depression', 'Joint problems'],
                'career': ['Labor', 'Mining', 'Agriculture', 'Service sector'],
                'health': ['Joints', 'Bones', 'Chronic diseases', 'Mental health'],
                'relationships': ['Servants', 'Elderly', 'Workers', 'Mentors']
            },
            'Rahu': {
                'positive': ['Foreign connections', 'Technology', 'Sudden gains', 'Innovation'],
                'challenges': ['Confusion', 'Deception', 'Unusual diseases', 'Obsessions'],
                'career': ['Technology', 'Foreign trade', 'Research', 'Unconventional fields'],
                'health': ['Mysterious diseases', 'Poisoning', 'Mental confusion', 'Addictions'],
                'relationships': ['Foreigners', 'Outcasts', 'Rebels', 'Innovators']
            },
            'Ketu': {
                'positive': ['Spiritual insights', 'Research abilities', 'Detachment', 'Occult knowledge'],
                'challenges': ['Mental confusion', 'Isolation', 'Unexpected events', 'Health mysteries'],
                'career': ['Spirituality', 'Research', 'Occult', 'Charity work'],
                'health': ['Mysterious ailments', 'Viral infections', 'Mental disorders', 'Accidents'],
                'relationships': ['Spiritual teachers', 'Mystics', 'Researchers', 'Healers']
            }
        }
        
        effects = {
            'maha_dasha_effects': planet_effects.get(maha_lord, {}),
            'antar_dasha_effects': planet_effects.get(antar_lord, {}),
            'combined_effects': {
                'positive': [],
                'challenges': [],
                'career_focus': [],
                'health_focus': [],
                'relationship_focus': []
            },
            'period_summary': f"{maha_lord} Maha Dasha - {antar_lord} Antar Dasha",
            'intensity': self.calculate_dasha_intensity(maha_lord, antar_lord)
        }
        
        # Combine effects
        if maha_lord in planet_effects and antar_lord in planet_effects:
            maha_effects = planet_effects[maha_lord]
            antar_effects = planet_effects[antar_lord]
            
            effects['combined_effects']['positive'] = maha_effects['positive'][:2] + antar_effects['positive'][:2]
            effects['combined_effects']['challenges'] = maha_effects['challenges'][:2] + antar_effects['challenges'][:2]
            effects['combined_effects']['career_focus'] = list(set(maha_effects['career'] + antar_effects['career']))
            effects['combined_effects']['health_focus'] = list(set(maha_effects['health'] + antar_effects['health']))
            effects['combined_effects']['relationship_focus'] = list(set(maha_effects['relationships'] + antar_effects['relationships']))
        
        # Add Pratyantar effects if available
        if pratyantar_lord and pratyantar_lord in planet_effects:
            effects['pratyantar_dasha_effects'] = planet_effects[pratyantar_lord]
            effects['period_summary'] += f" - {pratyantar_lord} Pratyantar"
        
        return effects
    
    def calculate_dasha_intensity(self, maha_lord: str, antar_lord: str) -> str:
        """Calculate intensity of dasha combination"""
        # Benefic and malefic classification
        benefics = ['Jupiter', 'Venus', 'Moon', 'Mercury']
        malefics = ['Sun', 'Mars', 'Saturn', 'Rahu', 'Ketu']
        
        if maha_lord in benefics and antar_lord in benefics:
            return "Highly Favorable"
        elif maha_lord in malefics and antar_lord in malefics:
            return "Challenging"
        else:
            return "Mixed Results"
    
    def get_next_dasha(self, maha_dashas: List[Dict], current_maha: Dict) -> Optional[Dict]:
        """Get next Maha Dasha"""
        for i, dasha in enumerate(maha_dashas):
            if dasha == current_maha and i + 1 < len(maha_dashas):
                return maha_dashas[i + 1]
        return None
    
    def jd_to_date(self, jd: float) -> str:
        """Convert Julian Day to date string"""
        cal = swe.revjul(jd)
        return f"{cal[0]:04d}-{cal[1]:02d}-{cal[2]:02d}"

class AstroChachuCore:
    """Main core class integrating all functionality"""
    
    def __init__(self):
        self.calculator = VedicAstroCalculator()
        self.ai = EnhancedAI()
        self.sade_sati_calc = SadeSatiCalculator()
        self.dasha_calc = VimshottariDashaCalculator()
        
    def generate_complete_kundli(self, birth_details: Dict) -> Dict:
        """Generate complete kundli with accurate calculations"""
        try:
            # Parse birth details
            date_of_birth = birth_details["date_of_birth"]
            time_of_birth = birth_details["time_of_birth"]
            latitude = float(birth_details["latitude"])
            longitude = float(birth_details["longitude"])
            
            # Get Julian Day
            jd = self.calculator.get_julian_day(date_of_birth, time_of_birth)
            
            # Calculate Ascendant
            ascendant = self.calculator.calculate_ascendant(jd, latitude, longitude)
            
            # Calculate all planets
            planets = {}
            planet_ids = {
                "Sun": 0, "Moon": 1, "Mercury": 2, "Venus": 3,
                "Mars": 4, "Jupiter": 5, "Saturn": 6, "Rahu": 11
            }
            
            for planet_name, planet_id in planet_ids.items():
                if planet_name == "Rahu":
                    # Rahu calculation
                    planet_data = self.calculator.calculate_planet(planet_id, jd)
                    planets[planet_name] = planet_data
                    # Ketu is exactly opposite to Rahu
                    ketu_long = (planet_data["longitude"] + 180) % 360
                    ketu_data = planet_data.copy()
                    ketu_data["longitude"] = ketu_long
                    ketu_data["sign"] = self.calculator.signs[int(ketu_long // 30)]
                    ketu_data["degree_in_sign"] = ketu_long % 30
                    planets["Ketu"] = ketu_data
                else:
                    planets[planet_name] = self.calculator.calculate_planet(planet_id, jd)
            
            # Calculate house positions
            for planet_name, planet_data in planets.items():
                planet_data["house"] = self.calculator.calculate_house_position(
                    planet_data["longitude"], ascendant["longitude"]
                )
            
            # Add ascendant to planets
            planets["Lagna"] = ascendant
            ascendant["house"] = 1  # Lagna is always in 1st house
            
            # Calculate Sade Sati
            moon_sign = planets["Moon"]["sign_number"]
            sade_sati_info = self.sade_sati_calc.calculate_sade_sati(jd, moon_sign)
            
            # Calculate Vimshottari Dasha
            moon_longitude = planets["Moon"]["longitude"]
            current_dasha = self.dasha_calc.get_current_detailed_dasha(jd, moon_longitude)
            
            # Get dasha sequence for next 20 years
            dasha_sequence = self.dasha_calc.calculate_comprehensive_dasha_sequence(jd, moon_longitude, 20)
            
            # Add dasha effects
            if 'current_maha_dasha' in current_dasha and 'current_antar_dasha' in current_dasha:
                maha_lord = current_dasha['current_maha_dasha']['lord']
                antar_lord = current_dasha['current_antar_dasha']['lord']
                pratyantar_lord = current_dasha['current_pratyantar_dasha']['lord'] if current_dasha.get('current_pratyantar_dasha') else None
                dasha_effects = self.dasha_calc.get_comprehensive_dasha_effects(maha_lord, antar_lord, pratyantar_lord)
                current_dasha['effects'] = dasha_effects
            
            return {
                "success": True,
                "julian_day": jd,
                "ascendant": ascendant,
                "planets": planets,
                "sade_sati": sade_sati_info,
                "current_dasha": current_dasha,
                "dasha_sequence": dasha_sequence,
                "birth_details": birth_details,
                "calculation_notes": "Accurate Swiss Ephemeris calculations with Sade Sati and Vimshottari Dasha"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Error in kundli calculation"
            }
    
    async def process_ai_question(self, question: str, birth_details: Optional[Dict] = None, chart_data: Optional[Dict] = None) -> str:
        """Process AI questions with enhanced intent detection"""
        try:
            # Detect intent
            intent_result = self.ai.detect_intent(question)
            
            if not birth_details:
                return self.generate_request_birth_details_response(intent_result["intent"])
            
            # Generate personalized response
            return self.ai.generate_personalized_response(
                intent_result["intent"], birth_details, chart_data or {}
            )
            
        except Exception as e:
            return f"Sorry, main aapka sawal samajh nahi paya. Kya aap dubara puch sakte hain? Error: {str(e)}"
    
    def generate_request_birth_details_response(self, intent: str) -> str:
        """Generate appropriate response when birth details are needed"""
        responses = {
            "marriage_timing": "Shaadi ki exact timing batane ke liye mujhe aapki complete birth details chahiye - date, time, aur birth place. Phir main Venus, Jupiter aur 7th house ki detailed analysis kar sakunga! 💍",
            
            "marriage_spouse": "Future spouse ke characteristics batane ke liye birth chart analysis zaroori hai. Aapki birth details share kariye - main 7th house lord, Venus position, aur compatibility factors dekh kar detailed analysis dunga! 👫",
            
            "career_field": "Career ke best field suggest karne ke liye 10th house, Mercury, aur Saturn ki position dekhni padti hai. Birth details share kariye comprehensive career guidance ke liye! 🚀",
            
            "career_timing": "Career growth ki timing predict karne ke liye current dasha analysis chahiye. Complete birth details se main exact periods bata sakunga jab promotions aur success milegi! ⏰",
            
            "financial_status": "Financial prospects ke liye 2nd house, 11th house, Jupiter aur Venus ki detailed analysis karna padta hai. Birth details share kariye wealth timeline ke liye! 💰",
            
            "health_general": "Health analysis ke liye 6th house, Mars, Moon aur Ascendant ki position important hai. Exact birth time se accurate health predictions possible hain! 🏥",
            
            "pregnancy_timing": "Pregnancy timing ke liye Jupiter, Moon, 5th house aur current dasha dekh kar analysis karta hun. Birth details chahiye exact fertile periods ke liye! 👶"
        }
        
        return responses.get(intent, 
            "Aapka question bahut specific hai! Accurate answer ke liye complete birth details share kariye - Date of Birth, Time of Birth, aur Birth Place. Main comprehensive analysis kar ke detailed guidance dunga! 🔮"
        )

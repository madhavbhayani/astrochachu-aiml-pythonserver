# -*- coding: utf-8 -*-
import threading
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
import os
import logging
from contextlib import asynccontextmanager
import random
import time
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional
import asyncio
import pytz
import swisseph as swe
from astral import LocationInfo
from astral.sun import sun
import psutil
import gc

class MemoryManager:
    def __init__(self, max_memory_mb: int = 30):
        self.max_memory_mb = max_memory_mb
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.active_requests = 0
        self.lock = threading.Lock()
        self.waiting_queue = asyncio.Queue()
        
    def get_current_memory_usage(self) -> int:
        """Get current memory usage in bytes"""
        process = psutil.Process()
        return process.memory_info().rss
    
    def get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB"""
        return self.get_current_memory_usage() / (1024 * 1024)
    
    async def acquire_memory_slot(self) -> bool:
        """Try to acquire a slot if memory allows"""
        current_memory = self.get_current_memory_usage()
        
        if current_memory < self.max_memory_bytes:
            with self.lock:
                self.active_requests += 1
            return True
        else:
            # Wait for memory to be available
            logger.warning(f"Memory limit reached: {current_memory / (1024 * 1024):.2f}MB. Waiting...")
            return False
    
    def release_memory_slot(self):
        """Release a memory slot and trigger garbage collection"""
        with self.lock:
            self.active_requests = max(0, self.active_requests - 1)
        
        # Force garbage collection
        gc.collect()
        
    def force_cleanup(self):
        """Force memory cleanup"""
        gc.collect()
        
    def get_stats(self) -> dict:
        """Get memory statistics"""
        return {
            "current_memory_mb": self.get_memory_usage_mb(),
            "max_memory_mb": self.max_memory_mb,
            "active_requests": self.active_requests,
            "memory_usage_percent": (self.get_memory_usage_mb() / self.max_memory_mb) * 100
        }

# Initialize global memory manager
memory_manager = MemoryManager(max_memory_mb=30)  # Set your RAM limit here

# Initialize Flask app
app = FastAPI(
    title="Horoscope API",
    description="API for Horoscope, Panchang, and Nakshatra predictions with multilingual support",
    version="1.0.0"
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set Swiss Ephemeris path
swe.set_ephe_path('/path/to/ephemeris')  # Update this path as needed

async def check_memory_limit():
    """Dependency to check memory before processing request"""
    max_wait_time = 30  # Maximum wait time in seconds
    wait_start = time.time()
    
    while time.time() - wait_start < max_wait_time:
        if await memory_manager.acquire_memory_slot():
            return True
        
        # Wait a bit before trying again
        await asyncio.sleep(0.5)
    
    # If we've waited too long, reject the request
    current_memory = memory_manager.get_memory_usage_mb()
    raise HTTPException(
        status_code=503,
        detail=f"Server overloaded. Current memory usage: {current_memory:.2f}MB. Please try again later."
    )

class MemoryCleanup:
    """Context manager for automatic memory cleanup"""
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        memory_manager.release_memory_slot()
        return False

class HoroscopeRequest(BaseModel):
    zodiac_sign: str = Field(..., description="Zodiac sign (Aries, Taurus, etc.)")
    language: str = Field("English", description="Language: English, Hindi, or Gujarati")
    type: str = Field("Daily", description="Prediction type: Daily, Weekly, Monthly, or Yearly")
    location: Dict[str, float] = Field(
        {"latitude": 0.0, "longitude": 0.0}, 
        description="Location coordinates"
    )

class PanchangRequest(BaseModel):
    date: Optional[str] = Field(None, description="Date in YYYY-MM-DD format")
    language: str = Field("English", description="Language: English, Hindi, or Gujarati")
    latitude: float = Field(23.0225, description="Latitude coordinate")
    longitude: float = Field(72.5714, description="Longitude coordinate")
    timezone: str = Field("Asia/Kolkata", description="Timezone")

class NakshatraRequest(BaseModel):
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    time: str = Field("12:00", description="Time in HH:MM format")
    latitude: float = Field(23.0225, description="Latitude coordinate")
    longitude: float = Field(72.5714, description="Longitude coordinate")
    timezone: str = Field("Asia/Kolkata", description="Timezone")
    language: str = Field("English", description="Language: English, Hindi, or Gujarati")
# Nakshatra data
NAKSHATRAS = [
    {
        "number": 1,
        "name": "Ashwini",
        "ruler": "Ketu",
        "deity": "Ashwini Kumaras",
        "symbol": "Horse's head",
        "qualities": "Energy, activity, enthusiasm, courage, healing abilities, and competitive spirit.",
        "description": "Ashwini is symbolized by a horse's head and ruled by Ketu. People born under this nakshatra are often quick, energetic, and enthusiastic. They excel in competitive environments, possess natural healing abilities, and have a strong desire for recognition. Ashwini brings qualities of intelligence, charm, and restlessness, making natives good at starting new ventures but sometimes impatient. It's auspicious for medical pursuits, transportation, sports, and quick endeavors."
    },
    {
        "number": 2,
        "name": "Bharani",
        "ruler": "Venus",
        "deity": "Yama (God of Death)",
        "symbol": "Yoni (Female Reproductive Organ)",
        "qualities": "Discipline, restraint, assertiveness, transformation, and creative potential.",
        "description": "Bharani is ruled by Venus and presided over by Yama, the god of death. This nakshatra represents the cycle of creation, maintenance, and dissolution. Bharani natives are often disciplined, determined, and possess strong creative energies. They excel in transforming circumstances and handling resources. This nakshatra supports activities related to cultivation, growth processes, financial management, and endeavors requiring perseverance and discipline."
    },
    {
        "number": 3,
        "name": "Krittika",
        "ruler": "Sun",
        "deity": "Agni (Fire God)",
        "symbol": "Razor or Flame",
        "qualities": "Purification, clarity, transformation, ambition, and leadership.",
        "description": "Krittika is ruled by the Sun and associated with Agni, the fire god. People born under this nakshatra often possess sharp intellect, strong ambition, and purifying energy. They can be brilliant, focused, and passionate about their pursuits. Krittika is favorable for activities requiring purification, leadership roles, analytical work, and transformative processes. Its energy supports clarity, precision, and the burning away of obstacles."
    },
    {
        "number": 4,
        "name": "Rohini",
        "ruler": "Moon",
        "deity": "Brahma (Creator)",
        "symbol": "Chariot or Ox-cart",
        "qualities": "Growth, fertility, prosperity, sensuality, and creativity.",
        "description": "Rohini is ruled by the Moon and associated with Lord Brahma. This nakshatra represents growth, nourishment, and material abundance. Natives of Rohini are often creative, sensual, and possess natural artistic talents. They value stability, beauty, and comfort. This nakshatra is excellent for activities related to agriculture, artistic pursuits, luxury industries, stable relationships, and endeavors requiring patience and sustained effort."
    },
    {
        "number": 5,
        "name": "Mrigashira",
        "ruler": "Mars",
        "deity": "Soma (Moon God)",
        "symbol": "Deer Head",
        "qualities": "Gentleness, curiosity, searching nature, adaptability, and communication skills.",
        "description": "Mrigashira is ruled by Mars and presided over by Soma. Symbolized by a deer's head, it represents the searching, gentle qualities of exploration and discovery. People born under this nakshatra are often curious, adaptable, and possess excellent communication skills. They have a natural ability to seek out knowledge and opportunities. Mrigashira supports research, exploration, communication-based ventures, travel, and pursuits requiring both gentleness and persistence."
    },
    {
        "number": 6,
        "name": "Ardra",
        "ruler": "Rahu",
        "deity": "Rudra (Storm God)",
        "symbol": "Teardrop or Diamond",
        "qualities": "Transformation through challenge, intensity, passion, and regenerative power.",
        "description": "Ardra is ruled by Rahu and associated with Rudra, the storm god. This powerful nakshatra represents transformation through intensity and challenge. Ardra natives often possess strong emotional depth, persistence through difficulties, and regenerative capabilities. They can be passionate, determined, and unafraid of life's storms. This nakshatra supports endeavors requiring breaking through obstacles, profound change, crisis management, and transformative healing."
    },
    {
        "number": 7,
        "name": "Punarvasu",
        "ruler": "Jupiter",
        "deity": "Aditi (Goddess of Boundlessness)",
        "symbol": "Bow or Quiver of Arrows",
        "qualities": "Renewal, optimism, wisdom, generosity, and expansiveness.",
        "description": "Punarvasu is ruled by Jupiter and presided over by Aditi, goddess of boundlessness. This nakshatra represents renewal, return to wealth, and expansive growth. People born under Punarvasu often possess natural wisdom, generosity, and optimistic outlook. They excel at bringing renewal to situations and seeing the broader perspective. This nakshatra supports education, spiritual pursuits, teaching, counseling, and ventures requiring wisdom, renewal, and positive growth."
    },
    {
        "number": 8,
        "name": "Pushya",
        "ruler": "Saturn",
        "deity": "Brihaspati (Jupiter)",
        "symbol": "Flower Basket or Udder",
        "qualities": "Nourishment, prosperity, spiritual growth, nurturing, and stability.",
        "description": "Pushya is ruled by Saturn and associated with Brihaspati. Considered one of the most auspicious nakshatras, it represents nourishment, prosperity, and spiritual abundance. Pushya natives are often nurturing, responsible, and possess strong moral values. They excel at creating stability and growth. This nakshatra is excellent for beginning important ventures, spiritual practices, charitable work, healing professions, and endeavors requiring integrity, nourishment, and sustained positive growth."
    },
    {
        "number": 9,
        "name": "Ashlesha",
        "ruler": "Mercury",
        "deity": "Naga (Serpent Gods)",
        "symbol": "Coiled Serpent",
        "qualities": "Intuition, mystical knowledge, healing abilities, intensity, and transformative power.",
        "description": "Ashlesha is ruled by Mercury and presided over by the Nagas. Symbolized by a coiled serpent, it represents kundalini energy, mystical knowledge, and penetrating insight. People born under this nakshatra often possess strong intuition, healing abilities, and magnetic personality. They have natural investigative skills and understand hidden matters. Ashlesha supports medical research, psychological work, occult studies, and endeavors requiring penetrating intelligence and transformative power."
    },
    {
        "number": 10,
        "name": "Magha",
        "ruler": "Ketu",
        "deity": "Pitris (Ancestors)",
        "symbol": "Throne or Royal Chamber",
        "qualities": "Leadership, power, ancestry, dignity, and social responsibility.",
        "description": "Magha is ruled by Ketu and associated with the Pitris, or ancestral spirits. This nakshatra represents power, leadership, and ancestral connections. Magha natives often possess natural authority, dignity, and a sense of duty to their lineage. They value honor and recognition. This nakshatra supports leadership roles, governmental work, ancestral healing, ceremonial activities, and ventures requiring public recognition, authority, and connection to tradition and heritage."
    },
    {
        "number": 11,
        "name": "Purva Phalguni",
        "ruler": "Venus",
        "deity": "Bhaga (God of Enjoyment)",
        "symbol": "Front Legs of a Bed or Hammock",
        "qualities": "Creativity, enjoyment, romance, social grace, and playfulness.",
        "description": "Purva Phalguni is ruled by Venus and presided over by Bhaga, god of enjoyment. This nakshatra represents creative expression, pleasure, and social harmony. People born under this nakshatra often possess charm, creativity, and natural social skills. They enjoy beauty and relationships. Purva Phalguni supports artistic endeavors, romance, entertainment, social activities, and ventures requiring creativity, pleasure, and harmonious social connections."
    },
    {
        "number": 12,
        "name": "Uttara Phalguni",
        "ruler": "Sun",
        "deity": "Aryaman (God of Contracts)",
        "symbol": "Back Legs of a Bed or Fig Tree",
        "qualities": "Balance, harmony, partnership, social contracts, and graceful power.",
        "description": "Uttara Phalguni is ruled by the Sun and associated with Aryaman, god of contracts and patronage. This nakshatra represents harmonious social relationships, beneficial agreements, and balanced partnerships. Natives of this nakshatra often value fairness, social harmony, and mutually beneficial relationships. They possess natural diplomatic abilities. This nakshatra supports marriage, contracts, partnerships, social networking, and endeavors requiring balance, integrity, and harmonious cooperation."
    },
    {
        "number": 13,
        "name": "Hasta",
        "ruler": "Moon",
        "deity": "Savitar (Aspect of Sun)",
        "symbol": "Hand or Fist",
        "qualities": "Skill, dexterity, healing abilities, practical intelligence, and manifestation.",
        "description": "Hasta is ruled by the Moon and presided over by Savitar. Symbolized by a hand, this nakshatra represents practical skills, craftsmanship, and manifesting ability. People born under Hasta often possess excellent manual dexterity, practical intelligence, and healing abilities. They excel at bringing ideas into form. This nakshatra supports craftsmanship, healing work, practical skills development, technological endeavors, and activities requiring precision, skill, and the ability to manifest ideas into reality."
    },
    {
        "number": 14,
        "name": "Chitra",
        "ruler": "Mars",
        "deity": "Vishvakarma (Divine Architect)",
        "symbol": "Pearl or Bright Jewel",
        "qualities": "Creativity, design skills, beauty, brilliance, and multi-faceted talents.",
        "description": "Chitra is ruled by Mars and associated with Vishvakarma, the divine architect. This nakshatra represents creative design, multi-faceted brilliance, and artistic excellence. Chitra natives often possess diverse talents, creative vision, and appreciation for beauty and design. They tend to stand out in whatever they do. This nakshatra supports design work, architecture, fashion, arts, strategic planning, and endeavors requiring creative brilliance, versatility, and visual excellence."
    },
    {
        "number": 15,
        "name": "Swati",
        "ruler": "Rahu",
        "deity": "Vayu (Wind God)",
        "symbol": "Coral or Young Sprout",
        "qualities": "Independence, adaptability, movement, self-sufficiency, and scattered brilliance.",
        "description": "Swati is ruled by Rahu and presided over by Vayu, god of wind. This nakshatra represents independent movement, self-sufficiency, and scattered brilliance. People born under Swati often possess adaptability, independent thinking, and movement-oriented talents. They value freedom and have an unpredictable quality. This nakshatra supports independent ventures, travel, aviation, communication, and endeavors requiring adaptability, independence, and the ability to spread ideas widely."
    },
    {
        "number": 16,
        "name": "Vishakha",
        "ruler": "Jupiter",
        "deity": "Indra-Agni (Gods of Power and Fire)",
        "symbol": "Triumphal Arch or Potter's Wheel",
        "qualities": "Determination, focus, goal achievement, leadership, and purposeful effort.",
        "description": "Vishakha is ruled by Jupiter and associated with Indra-Agni. This nakshatra represents focused determination, purposeful effort, and achievement of goals. Vishakha natives are often ambitious, determined, and possess leadership qualities combined with spiritual focus. They excel at achieving objectives through sustained effort. This nakshatra supports goal-setting, leadership roles, competitive activities, spiritual pursuits with practical aims, and endeavors requiring determination, focus, and strategic achievement."
    },
    {
        "number": 17,
        "name": "Anuradha",
        "ruler": "Saturn",
        "deity": "Mitra (God of Friendship)",
        "symbol": "Lotus or Staff",
        "qualities": "Friendship, cooperation, devotion, loyalty, and success through relationships.",
        "description": "Anuradha is ruled by Saturn and presided over by Mitra, god of friendship. This nakshatra represents successful cooperation, friendship, and devotion. People born under Anuradha often possess natural diplomatic skills, loyalty, and ability to succeed through harmonious relationships. They value friendship and cooperation. This nakshatra supports teamwork, diplomatic endeavors, friendship-based ventures, devotional practices, and activities requiring cooperation, loyalty, and mutual success."
    },
    {
        "number": 18,
        "name": "Jyeshtha",
        "ruler": "Mercury",
        "deity": "Indra (King of Gods)",
        "symbol": "Earring or Umbrella",
        "qualities": "Courage, leadership, protective qualities, seniority, and power.",
        "description": "Jyeshtha is ruled by Mercury and associated with Indra, king of the gods. This nakshatra represents seniority, protective leadership, and courage. Jyeshtha natives often possess natural leadership abilities, protective instincts, and desire for recognition. They have strong personalities and sense of authority. This nakshatra supports leadership roles, protective services, senior positions, mentorship, and endeavors requiring courage, protection of others, and the wielding of authority with intelligence."
    },
    {
        "number": 19,
        "name": "Mula",
        "ruler": "Ketu",
        "deity": "Nirriti (Goddess of Destruction)",
        "symbol": "Tied Bunch of Roots or Lion's Tail",
        "qualities": "Destruction for creation, getting to the root, intensity, and transformative power.",
        "description": "Mula is ruled by Ketu and presided over by Nirriti. Its name means 'root' and it represents the destructive power that precedes creation. People born under Mula often possess investigative abilities, interest in fundamental principles, and transformative energy. They can get to the root of matters. This nakshatra supports research, elimination of obstacles, fundamental change, spiritual pursuits, and endeavors requiring deep investigation, uprooting of problems, and complete transformation."
    },
    {
        "number": 20,
        "name": "Purva Ashadha",
        "ruler": "Venus",
        "deity": "Apas (Water Goddesses)",
        "symbol": "Fan or Tusk",
        "qualities": "Early victory, invigoration, purification, and unquenchable energy.",
        "description": "Purva Ashadha is ruled by Venus and associated with Apas, the water goddesses. This nakshatra represents early victory, invigoration, and unquenchable energy. Purva Ashadha natives often possess determination, enthusiasm, and ability to overcome obstacles through sustained effort. They have purifying energy and natural leadership. This nakshatra supports initial phases of important projects, leadership roles, water-related activities, and endeavors requiring determination, purification, and invincible enthusiasm."
    },
    {
        "number": 21,
        "name": "Uttara Ashadha",
        "ruler": "Sun",
        "deity": "Vishvedevas (Universal Gods)",
        "symbol": "Elephant Tusk or Planks of a Bed",
        "qualities": "Universal principles, later victory, balance of power, and enduring success.",
        "description": "Uttara Ashadha is ruled by the Sun and presided over by the Vishvedevas. This nakshatra represents later victory, universal principles, and balanced power. People born under this nakshatra often possess strong principles, balanced leadership abilities, and capacity for enduring success. They value universal truths and lasting achievement. This nakshatra supports long-term projects, ethical leadership, philosophical pursuits, and endeavors requiring principled action, balanced power, and sustained, honorable success."
    },
    {
        "number": 22,
        "name": "Shravana",
        "ruler": "Moon",
        "deity": "Vishnu",
        "symbol": "Ear or Three Footprints",
        "qualities": "Learning, wisdom through listening, connectivity, devotion, and fame.",
        "description": "Shravana is ruled by the Moon and associated with Lord Vishnu. Its name relates to hearing and it represents learning through listening, connectivity, and devotion. Shravana natives often possess excellent listening skills, learning abilities, and connective intelligence. They value wisdom and harmonious relationships. This nakshatra supports education, communication, devotional practices, networking, and endeavors requiring good listening, wisdom gathering, connectivity, and the harmonizing of diverse elements."
    },
    {
        "number": 23,
        "name": "Dhanishta",
        "ruler": "Mars",
        "deity": "Vasus (Gods of Abundance)",
        "symbol": "Drum or Flute",
        "qualities": "Wealth, abundance, music, rhythm, and generous spirit.",
        "description": "Dhanishta is ruled by Mars and presided over by the Vasus. This nakshatra represents wealth, rhythm, music, and generous abundance. People born under Dhanishta often possess musical talents, rhythmic abilities, and natural generosity. They have a prosperous energy and ability to create wealth. This nakshatra supports musical endeavors, wealth creation, philanthropic activities, and ventures requiring rhythm, momentum, prosperous energy, and the generous sharing of abundance."
    },
    {
        "number": 24,
        "name": "Shatabhisha",
        "ruler": "Rahu",
        "deity": "Varuna (God of Cosmic Waters)",
        "symbol": "Empty Circle or Flower",
        "qualities": "Healing, scientific mind, independence, mystical abilities, and expansive awareness.",
        "description": "Shatabhisha is ruled by Rahu and associated with Varuna. Its name means 'hundred healers' and it represents healing powers, scientific understanding, and cosmic awareness. Shatabhisha natives often possess innovative thinking, healing abilities, and independent perspective. They can perceive beyond conventional boundaries. This nakshatra supports medical practices, scientific research, alternative healing, mystical pursuits, and endeavors requiring innovation, independence of thought, and broad awareness of interconnected systems."
    },
    {
        "number": 25,
        "name": "Purva Bhadrapada",
        "ruler": "Jupiter",
        "deity": "Aja Ekapada (One-footed Goat)",
        "symbol": "Two-faced Man or Front of Funeral Cot",
        "qualities": "Intensity, fiery wisdom, transformative vision, and spiritual awakening.",
        "description": "Purva Bhadrapada is ruled by Jupiter and presided over by Aja Ekapada. This nakshatra represents fiery wisdom, intensity, and spiritual awakening through challenge. People born under this nakshatra often possess penetrating insight, transformative vision, and ability to inspire others. They can be intensely focused on their path. This nakshatra supports spiritual pursuits, inspirational leadership, transformative teaching, and endeavors requiring intensity, deep wisdom, and the courage to walk a unique spiritual path."
    },
    {
        "number": 26,
        "name": "Uttara Bhadrapada",
        "ruler": "Saturn",
        "deity": "Ahirbudhnya (Serpent of the Depths)",
        "symbol": "Twin or Back Legs of Funeral Cot",
        "qualities": "Deep truth, profound wisdom, serpentine power, and regenerative abilities.",
        "description": "Uttara Bhadrapada is ruled by Saturn and associated with Ahirbudhnya. This nakshatra represents deep truth, serpentine wisdom, and regenerative power from the depths. Uttara Bhadrapada natives often possess profound understanding, regenerative abilities, and capacity to bring hidden truths to light. They value depth and authenticity. This nakshatra supports deep research, psychological work, spiritual transformation, and endeavors requiring profound wisdom, regenerative power, and the ability to work with hidden forces."
    },
    {
        "number": 27,
        "name": "Revati",
        "ruler": "Mercury",
        "deity": "Pushan (Nourishing God)",
        "symbol": "Fish or Drum",
        "qualities": "Nourishment, protection during transitions, abundance, and nurturing wisdom.",
        "description": "Revati is ruled by Mercury and presided over by Pushan. As the final nakshatra, it represents completion, nourishment, and protection during transitions. People born under Revati often possess nurturing qualities, protective wisdom, and ability to nourish others across transitions. They tend to be caring and supportive. This nakshatra supports completion of cycles, nurturing activities, transitional guidance, and endeavors requiring gentle wisdom, nourishing qualities, and the ability to help others move smoothly through life's transitions."
    }
]

# Define degrees for each nakshatra (in lunar longitude)
NAKSHATRA_DEGREES = {
    "Ashwini": (0, 13.20),
    "Bharani": (13.20, 26.40),
    "Krittika": (26.40, 40.00),
    "Rohini": (40.00, 53.20),
    "Mrigashira": (53.20, 66.40),
    "Ardra": (66.40, 80.00),
    "Punarvasu": (80.00, 93.20),
    "Pushya": (93.20, 106.40),
    "Ashlesha": (106.40, 120.00),
    "Magha": (120.00, 133.20),
    "Purva Phalguni": (133.20, 146.40),
    "Uttara Phalguni": (146.40, 160.00),
    "Hasta": (160.00, 173.20),
    "Chitra": (173.20, 186.40),
    "Swati": (186.40, 200.00),
    "Vishakha": (200.00, 213.20),
    "Anuradha": (213.20, 226.40),
    "Jyeshtha": (226.40, 240.00),
    "Mula": (240.00, 253.20),
    "Purva Ashadha": (253.20, 266.40),
    "Uttara Ashadha": (266.40, 280.00),
    "Shravana": (280.00, 293.20),
    "Dhanishta": (293.20, 306.40),
    "Shatabhisha": (306.40, 320.00),
    "Purva Bhadrapada": (320.00, 333.20),
    "Uttara Bhadrapada": (333.20, 346.40),
    "Revati": (346.40, 360.00)
}

# Tithi (lunar day) information
TITHIS = [
    {
        "number": 1,
        "name": "Shukla Pratipada",
        "paksha": "Shukla",
        "deity": "Agni",
        "special": "Auspicious for rituals, marriage, travel",
        "description": "Good for starting new ventures and projects. Favorable for planning and organization. Avoid excessive physical exertion and arguments."
    },
    {
        "number": 2,
        "name": "Shukla Dwitiya",
        "paksha": "Shukla",
        "deity": "Brahma",
        "special": "Good for housework, learning",
        "description": "Excellent for intellectual pursuits and learning. Suitable for purchases and agreements. Avoid unnecessary travel and overindulgence."
    },
    {
        "number": 3,
        "name": "Shukla Tritiya",
        "paksha": "Shukla",
        "deity": "Parvati",
        "special": "Celebrated as Gauri Tritiya (Teej)",
        "description": "Auspicious for all undertakings, especially weddings and partnerships. Benefits from charitable activities. Avoid conflicts and hasty decisions."
    },
    {
        "number": 4,
        "name": "Shukla Chaturthi",
        "paksha": "Shukla",
        "deity": "Ganesha",
        "special": "Sankashti/Ganesh Chaturthi",
        "description": "Good for worship of Lord Ganesha and removing obstacles. Favorable for creative endeavors. Avoid starting major projects or signing contracts."
    },
    {
        "number": 5,
        "name": "Shukla Panchami",
        "paksha": "Shukla",
        "deity": "Naga Devata",
        "special": "Nag Panchami, Saraswati Puja",
        "description": "Excellent for education, arts, and knowledge acquisition. Good for competitions and tests. Avoid unnecessary arguments and rash decisions."
    },
    {
        "number": 6,
        "name": "Shukla Shashthi",
        "paksha": "Shukla",
        "deity": "Kartikeya",
        "special": "Skanda Shashthi, children's health",
        "description": "Favorable for victory over enemies and completion of difficult tasks. Good for health initiatives. Avoid procrastination and indecisiveness."
    },
    {
        "number": 7,
        "name": "Shukla Saptami",
        "paksha": "Shukla",
        "deity": "Surya",
        "special": "Ratha Saptami, start of auspicious work",
        "description": "Excellent for health, vitality, and leadership activities. Good for starting treatments. Avoid excessive sun exposure and ego conflicts."
    },
    {
        "number": 8,
        "name": "Shukla Ashtami",
        "paksha": "Shukla",
        "deity": "Shiva",
        "special": "Kala Ashtami, Durga Puja",
        "description": "Good for meditation, spiritual practices, and self-transformation. Favorable for fasting. Avoid impulsive decisions and major changes."
    },
    {
        "number": 9,
        "name": "Shukla Navami",
        "paksha": "Shukla",
        "deity": "Durga",
        "special": "Mahanavami, victory over evil",
        "description": "Powerful for spiritual practices and overcoming challenges. Good for courage and strength. Avoid unnecessary risks and confrontations."
    },
    {
        "number": 10,
        "name": "Shukla Dashami",
        "paksha": "Shukla",
        "deity": "Dharma",
        "special": "Vijayadashami/Dussehra",
        "description": "Favorable for righteous actions and religious ceremonies. Good for ethical decisions. Avoid dishonesty and unethical compromises."
    },
    {
        "number": 11,
        "name": "Shukla Ekadashi",
        "paksha": "Shukla",
        "deity": "Vishnu",
        "special": "Fasting day, spiritually uplifting",
        "description": "Highly auspicious for spiritual practices, fasting, and worship of Vishnu. Benefits from restraint and self-control. Avoid overeating and sensual indulgences."
    },
    {
        "number": 12,
        "name": "Shukla Dwadashi",
        "paksha": "Shukla",
        "deity": "Vishnu",
        "special": "Breaking Ekadashi fast (Parana)",
        "description": "Good for breaking fasts and charitable activities. Favorable for generosity and giving. Avoid selfishness and stubbornness today."
    },
    {
        "number": 13,
        "name": "Shukla Trayodashi",
        "paksha": "Shukla",
        "deity": "Shiva",
        "special": "Pradosh Vrat, Dhanteras",
        "description": "Excellent for beauty treatments, romance, and artistic pursuits. Good for sensual pleasures. Avoid excessive attachment and jealousy."
    },
    {
        "number": 14,
        "name": "Shukla Chaturdashi",
        "paksha": "Shukla",
        "deity": "Kali, Rudra ",
        "special": "Narak Chaturdashi, spiritual cleansing",
        "description": "Powerful for worship of Lord Shiva and spiritual growth. Good for finishing tasks. Avoid beginning major projects and hasty conclusions."
    },
    {
        "number": 15,
        "name": "Purnima",
        "paksha": "Shukla",
        "deity": "Chandra",
        "special": "Waxing phase of the moon (new to full moon)",
        "description": "Highly auspicious for spiritual practices, especially related to the moon. Full emotional and mental strength. Avoid emotional instability and overthinking."
    },
    {
        "number": 16,
        "name": "Krishna Pratipada",
        "paksha": "Krishna",
        "deity": "Agni",
        "special": "Auspicious for rituals, marriage, travel",
        "description": "Suitable for planning and reflection. Good for introspection and simple rituals. Avoid major launches or important beginnings."
    },
    {
        "number": 17,
        "name": "Krishna Dwitiya",
        "paksha": "Krishna",
        "deity": "Brahma",
        "special": "Good for housework, learning",
        "description": "Favorable for intellectual pursuits and analytical work. Good for research and study. Avoid impulsive decisions and confrontations."
    },
    {
        "number": 18,
        "name": "Krishna Tritiya",
        "paksha": "Krishna",
        "deity": "Parvati",
        "special": "Celebrated as Gauri Tritiya (Teej)",
        "description": "Good for activities requiring courage and determination. Favorable for assertive actions. Avoid aggression and unnecessary force."
    },
    {
        "number": 19,
        "name": "Krishna Chaturthi",
        "paksha": "Krishna",
        "deity": "Ganesha",
        "special": "Sankashti/Ganesh Chaturthi",
        "description": "Suitable for removing obstacles and solving problems. Good for analytical thinking. Avoid starting new ventures and major purchases."
    },
    {
        "number": 20,
        "name": "Krishna Panchami",
        "paksha": "Krishna",
        "deity": "Naga Devata",
        "special": "Nag Panchami, Saraswati Puja",
        "description": "Favorable for education, learning new skills, and artistic pursuits. Good for communication. Avoid arguments and misunderstandings."
    },
    {
        "number": 21,
        "name": "Krishna Shashthi",
        "paksha": "Krishna",
        "deity": "Kartikeya",
        "special": "Skanda Shashthi, children's health",
        "description": "Good for competitive activities and overcoming challenges. Favorable for strategic planning. Avoid conflict and excessive competition."
    },
    {
        "number": 22,
        "name": "Krishna Saptami",
        "paksha": "Krishna",
        "deity": "Surya",
        "special": "Ratha Saptami, start of auspicious work",
        "description": "Suitable for health treatments and healing. Good for physical activities and exercise. Avoid overexertion and risky ventures."
    },
    {
        "number": 23,
        "name": "Krishna Ashtami",
        "paksha": "Krishna",
        "deity": "Durga",
        "special": "Kala Ashtami, Durga Puja",
        "description": "Powerful for devotional activities, especially to Lord Krishna. Good for fasting and spiritual practices. Avoid excessive materialism and sensual indulgence."
    },
    {
        "number": 24,
        "name": "Krishna Navami",
        "paksha": "Krishna",
        "deity": "Durga",
        "special": "Mahanavami, victory over evil",
        "description": "Favorable for protective measures and strengthening security. Good for courage and determination. Avoid unnecessary risks and fears."
    },
    {
        "number": 25,
        "name": "Krishna Dashami",
        "paksha": "Krishna",
        "deity": "Dharma",
        "special": "Vijayadashami/Dussehra",
        "description": "Good for ethical decisions and righteous actions. Favorable for legal matters. Avoid dishonesty and unethical compromises."
    },
    {
        "number": 26,
        "name": "Krishna Ekadashi",
        "paksha": "Krishna",
        "deity": "Vishnu",
        "special": "Fasting day, spiritually uplifting",
        "description": "Highly auspicious for fasting and spiritual practices. Good for detachment and self-control. Avoid overindulgence and material attachment."
    },
    {
        "number": 27,
        "name": "Krishna Dwadashi",
        "paksha": "Krishna",
        "deity": "Vishnu",
        "special": "Breaking Ekadashi fast (Parana)",
        "description": "Favorable for breaking fasts and charitable activities. Good for generosity and giving. Avoid starting new projects and major decisions."
    },
    {
        "number": 28,
        "name": "Krishna Trayodashi",
        "paksha": "Krishna",
        "deity": "Shiva",
        "special": "Pradosh Vrat, Dhanteras",
        "description": "Powerful for spiritual practices, especially those related to transformation. Good for overcoming challenges. Avoid fear and negative thinking."
    },
    {
        "number": 29,
        "name": "Krishna Chaturdashi",
        "paksha": "Krishna",
        "deity": "Kali",
        "special": "Narak Chaturdashi, spiritual cleansing",
        "description": "Suitable for removing obstacles and ending negative influences. Good for spiritual cleansing. Avoid dark places and negative company."
    },
    {
        "number": 30,
        "name": "Amavasya",
        "paksha": "Krishna",
        "deity": "Pitri",
        "special": "Waning phase (full to new moon)",
        "description": "Powerful for ancestral worship and ending karmic cycles. Good for meditation and inner work. Avoid major beginnings and public activities."
    }
]

# Hindu months
HINDU_MONTHS = [
    "Chaitra", "Vaisakha", "Jyeshtha", "Ashadha", 
    "Shravana", "Bhadrapada", "Ashwin", "Kartika", 
    "Margashirsha", "Pausha", "Magha", "Phalguna"
]

# Yoga information (sum of sun and moon longitudes / 13°20')
YOGAS = [
    {
        "number": 1,
        "name": "Vishkambha",
        "meaning": "Pillar or Support",
        "speciality": "Obstacles, challenges that lead to strength"
    },
    {
        "number": 2,
        "name": "Priti",
        "meaning": "Love and Joy",
        "speciality": "Excellent for relationships and pleasant activities"
    },
    {
        "number": 3,
        "name": "Ayushman",
        "meaning": "Longevity and Health",
        "speciality": "Good for medical treatments and health initiatives"
    },
    {
        "number": 4,
        "name": "Saubhagya",
        "meaning": "Good Fortune and Prosperity",
        "speciality": "Auspicious for financial matters and prosperity"
    },
    {
        "number": 5,
        "name": "Shobhana",
        "meaning": "Beauty and Splendor",
        "speciality": "Favorable for artistic pursuits and aesthetics"
    },
    {
        "number": 6,
        "name": "Atiganda",
        "meaning": "Extreme Danger",
        "speciality": "Challenging; best for cautious and reflective activities"
    },
    {
        "number": 7,
        "name": "Sukarman",
        "meaning": "Good Action",
        "speciality": "Excellent for all virtuous and important actions"
    },
    {
        "number": 8,
        "name": "Dhriti",
        "meaning": "Steadiness and Determination",
        "speciality": "Good for activities requiring persistence and stability"
    },
    {
        "number": 9,
        "name": "Shula",
        "meaning": "Spear or Pain",
        "speciality": "Challenging; good for decisive and courageous actions"
    },
    {
        "number": 10,
        "name": "Ganda",
        "meaning": "Obstacle or Problem",
        "speciality": "Difficult; best for solving problems and removing obstacles"
    },
    {
        "number": 11,
        "name": "Vriddhi",
        "meaning": "Growth and Prosperity",
        "speciality": "Excellent for growth-oriented activities and investments"
    },
    {
        "number": 12,
        "name": "Dhruva",
        "meaning": "Fixed and Permanent",
        "speciality": "Good for activities requiring stability and endurance"
    },
    {
        "number": 13,
        "name": "Vyaghata",
        "meaning": "Obstruction or Danger",
        "speciality": "Challenging; requires careful planning and execution"
    },
    {
        "number": 14,
        "name": "Harshana",
        "meaning": "Joy and Happiness",
        "speciality": "Favorable for celebrations and enjoyable activities"
    },
    {
        "number": 15,
        "name": "Vajra",
        "meaning": "Thunderbolt or Diamond",
        "speciality": "Powerful but unstable; good for forceful actions"
    },
    {
        "number": 16,
        "name": "Siddhi",
        "meaning": "Success and Accomplishment",
        "speciality": "Highly auspicious for all important undertakings"
    },
    {
        "number": 17,
        "name": "Vyatipata",
        "meaning": "Calamity or Disaster",
        "speciality": "Challenging; best for spiritual practices and caution"
    },
    {
        "number": 18,
        "name": "Variyana",
        "meaning": "Superior or Excellent",
        "speciality": "Good for bold actions and leadership initiatives"
    },
    {
        "number": 19,
        "name": "Parigha",
        "meaning": "Obstacle or Hindrance",
        "speciality": "Difficult; better for routine activities and patience"
    },
    {
        "number": 20,
        "name": "Shiva",
        "meaning": "Auspicious and Beneficial",
        "speciality": "Excellent for all positive and important undertakings"
    },
    {
        "number": 21,
        "name": "Siddha",
        "meaning": "Accomplished or Perfected",
        "speciality": "Highly favorable for all significant activities"
    },
    {
        "number": 22,
        "name": "Sadhya",
        "meaning": "Accomplishable or Achievable",
        "speciality": "Good for activities that can be completed quickly"
    },
    {
        "number": 23,
        "name": "Shubha",
        "meaning": "Auspicious and Fortunate",
        "speciality": "Excellent for all auspicious and important activities"
    },
    {
        "number": 24,
        "name": "Shukla",
        "meaning": "Bright and Pure",
        "speciality": "Favorable for spirituality and pure intentions"
    },
    {
        "number": 25,
        "name": "Brahma",
        "meaning": "Creative and Divine",
        "speciality": "Excellent for creative pursuits and spiritual activities"
    },
    {
        "number": 26,
        "name": "Indra",
        "meaning": "Leadership and Power",
        "speciality": "Good for leadership activities and positions of authority"
    },
    {
        "number": 27,
        "name": "Vaidhriti",
        "meaning": "Separation or Division",
        "speciality": "Challenging; best for contemplation and careful planning"
    }
]

# Constants
ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", 
    "Leo", "Virgo", "Libra", "Scorpio", 
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

# Dictionary of planets with simple IDs instead of const references
PLANETS = {
    "Sun": {"id": "SUN", "name": "Sun"},
    "Moon": {"id": "MOON", "name": "Moon"},
    "Mercury": {"id": "MERCURY", "name": "Mercury"},
    "Venus": {"id": "VENUS", "name": "Venus"},
    "Mars": {"id": "MARS", "name": "Mars"},
    "Jupiter": {"id": "JUPITER", "name": "Jupiter"},
    "Saturn": {"id": "SATURN", "name": "Saturn"},
    "Uranus": {"id": "URANUS", "name": "Uranus"},
    "Neptune": {"id": "NEPTUNE", "name": "Neptune"},
    "Pluto": {"id": "PLUTO", "name": "Pluto"}
}

# Zodiac element associations
ZODIAC_ELEMENTS = {
    "Aries": "Fire",
    "Taurus": "Earth",
    "Gemini": "Air",
    "Cancer": "Water", 
    "Leo": "Fire",
    "Virgo": "Earth",
    "Libra": "Air",
    "Scorpio": "Water",
    "Sagittarius": "Fire",
    "Capricorn": "Earth",
    "Aquarius": "Air",
    "Pisces": "Water"
}

# Zodiac ruling planets
RULING_PLANETS = {
    "Aries": "Mars",
    "Taurus": "Venus",
    "Gemini": "Mercury",
    "Cancer": "Moon",
    "Leo": "Sun",
    "Virgo": "Mercury",
    "Libra": "Venus",
    "Scorpio": "Pluto",
    "Sagittarius": "Jupiter",
    "Capricorn": "Saturn",
    "Aquarius": "Uranus",
    "Pisces": "Neptune"
}

# Lucky colors by zodiac sign
LUCKY_COLORS = {
    "Aries": ["Red", "Orange", "Yellow"],
    "Taurus": ["Green", "Pink", "Blue"],
    "Gemini": ["Yellow", "Silver", "Gray"],
    "Cancer": ["White", "Silver", "Blue"],
    "Leo": ["Gold", "Orange", "Red"],
    "Virgo": ["Navy", "Gray", "Brown"],
    "Libra": ["Pink", "Blue", "Green"],
    "Scorpio": ["Red", "Black", "Maroon"],
    "Sagittarius": ["Purple", "Turquoise", "Yellow"],
    "Capricorn": ["Black", "Brown", "Gray"],
    "Aquarius": ["Blue", "Silver", "Aqua"],
    "Pisces": ["Sea Green", "Purple", "White"]
}

# Lucky numbers by zodiac sign
LUCKY_NUMBERS = {
    "Aries": [1, 8, 17],
    "Taurus": [2, 6, 9],
    "Gemini": [5, 7, 14],
    "Cancer": [2, 7, 11],
    "Leo": [1, 3, 10],
    "Virgo": [3, 8, 16],
    "Libra": [4, 6, 15],
    "Scorpio": [4, 13, 21],
    "Sagittarius": [3, 9, 22],
    "Capricorn": [6, 8, 26],
    "Aquarius": [4, 7, 11],
    "Pisces": [3, 9, 12]
}

# Choghadiya and Hora related constants
WEEKDAY_TO_PLANET = {
    0: "Moon",     # Monday
    1: "Mars",     # Tuesday
    2: "Mercury",  # Wednesday
    3: "Jupiter",  # Thursday
    4: "Venus",    # Friday
    5: "Saturn",   # Saturday
    6: "Sun"       # Sunday
}

HORA_SEQUENCE = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"]

PLANET_TO_CHOGHADIYA = {
    "Sun": {"name": "Udveg", "nature": "Neutral"},
    "Venus": {"name": "Char", "nature": "Good"},
    "Mercury": {"name": "Labh", "nature": "Good"},
    "Moon": {"name": "Amrit", "nature": "Good"},
    "Saturn": {"name": "Kaal", "nature": "Bad"},
    "Jupiter": {"name": "Shubh", "nature": "Good"},
    "Mars": {"name": "Rog", "nature": "Bad"}
}

CHOGHADIYA_MEANINGS = {
    "Amrit": "Nectar - Most auspicious for all activities",
    "Shubh": "Auspicious - Good for all positive activities",
    "Labh": "Profit - Excellent for business and financial matters",
    "Char": "Movement - Good for travel and dynamic activities",
    "Kaal": "Death - Inauspicious, avoid important activities",
    "Rog": "Disease - Avoid health-related decisions",
    "Udveg": "Anxiety - Mixed results, proceed with caution"
}

PLANET_HORA_PROPERTIES = {
    "Sun": {"nature": "Good", "meaning": "Authority, leadership, government work"},
    "Moon": {"nature": "Good", "meaning": "Emotions, family matters, water-related activities"},
    "Mars": {"nature": "Neutral", "meaning": "Energy, sports, real estate, surgery"},
    "Mercury": {"nature": "Good", "meaning": "Communication, education, business, travel"},
    "Jupiter": {"nature": "Excellent", "meaning": "Wisdom, spirituality, teaching, ceremonies"},
    "Venus": {"nature": "Excellent", "meaning": "Arts, beauty, relationships, luxury"},
    "Saturn": {"nature": "Bad", "meaning": "Delays, obstacles, hard work, patience required"}
}



def get_planetary_positions(date: datetime, lat: float, lon: float) -> Dict[str, Dict[str, Any]]:
    """Calculate planetary positions using a simple deterministic approach"""
    try:
        jd = swe.julday(date.year, date.month, date.day, date.hour + date.minute/60)
        
        positions = {}
        planets = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS, swe.JUPITER, swe.SATURN]
        planet_names = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
        
        for i, planet in enumerate(planets):
            try:
                result = swe.calc_ut(jd, planet, swe.FLG_SWIEPH)
                longitude = result[0][0]
                
                # Convert longitude to zodiac sign
                sign_num = int(longitude / 30)
                sign_names = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                             "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
                sign = sign_names[sign_num]
                
                positions[planet_names[i]] = {
                    "longitude": round(longitude, 2),
                    "sign": sign,
                    "degree": round(longitude % 30, 2)
                }
            except Exception as e:
                logger.error(f"Error calculating position for {planet_names[i]}: {e}")
                positions[planet_names[i]] = {
                    "longitude": 0.0,
                    "sign": "Aries",
                    "degree": 0.0
                }
        
        return positions
    
    except Exception as e:
        logger.error(f"Error in get_planetary_positions: {e}")
        return {}

def generate_aspect_influences(planetary_positions: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate information about planetary aspects and their influences"""
    aspects = []
    
    # Check if planetary_positions is None or empty
    if not planetary_positions:
        return aspects
    
    # Define major aspects and their orbs (allowed deviation in degrees)
    aspect_types = {
        "Conjunction": {"angle": 0, "orb": 8, "influence": "strong"},
        "Opposition": {"angle": 180, "orb": 8, "influence": "challenging"},
        "Trine": {"angle": 120, "orb": 8, "influence": "harmonious"},
        "Square": {"angle": 90, "orb": 7, "influence": "tense"},
        "Sextile": {"angle": 60, "orb": 6, "influence": "favorable"}
    }
    
    # Check each planet pair for aspects
    planets = list(planetary_positions.keys())
    for i in range(len(planets)):
        for j in range(i + 1, len(planets)):
            planet1 = planets[i]
            planet2 = planets[j]
            
            pos1 = planetary_positions.get(planet1)
            pos2 = planetary_positions.get(planet2)
            
            # Skip if either position is None or empty
            if not pos1 or not pos2:
                continue
                
            long1 = pos1.get("longitude", 0)
            long2 = pos2.get("longitude", 0)
            
            # Skip if longitudes are None
            if long1 is None or long2 is None:
                continue
            
            # Calculate angular difference
            diff = abs(long1 - long2)
            if diff > 180:
                diff = 360 - diff
            
            # Check for aspects
            for aspect_name, aspect_info in aspect_types.items():
                target_angle = aspect_info["angle"]
                orb = aspect_info["orb"]
                
                if abs(diff - target_angle) <= orb:
                    exact = abs(diff - target_angle) < 2
                    
                    aspect = {
                        "planets": [planet1, planet2],
                        "aspect": aspect_name,
                        "angle": round(diff, 2),
                        "orb": round(abs(diff - target_angle), 2),
                        "exact": exact,
                        "influence_type": aspect_info["influence"],
                        "description": generate_aspect_description(planet1, planet2, aspect_name)
                    }
                    aspects.append(aspect)
                    break
    
    return aspects

def generate_aspect_description(planet1: str, planet2: str, aspect: str) -> str:
    """Generate a description of the influence of an aspect between two planets"""
    
    # Dictionary of planetary influences
    planet_influences = {
        "Sun": "identity, ego, vitality",
        "Moon": "emotions, instincts, unconscious reactions",
        "Mercury": "communication, thinking, learning",
        "Venus": "love, beauty, values, attraction",
        "Mars": "energy, action, desire, courage",
        "Jupiter": "expansion, growth, optimism, luck",
        "Saturn": "discipline, responsibility, limitations",
        "Uranus": "innovation, rebellion, sudden changes",
        "Neptune": "dreams, spirituality, illusion",
        "Pluto": "transformation, power, rebirth"
    }
    
    # Dictionary of aspect influences
    aspect_influences = {
        "Conjunction": "combines and intensifies the energy of",
        "Opposition": "creates tension and awareness between",
        "Trine": "creates harmony and flow between",
        "Square": "creates challenges and growth opportunities between",
        "Sextile": "creates opportunities and ease of expression between"
    }
    
    descriptions = [
        f"The {aspect} between {planet1} and {planet2} {aspect_influences.get(aspect, 'influences')} your {planet_influences.get(planet1, 'energy')} and {planet_influences.get(planet2, 'energy')}.",
        f"With {planet1} in {aspect} to {planet2}, you may experience a connection of {planet_influences.get(planet1, 'energy')} with {planet_influences.get(planet2, 'energy')}.",
        f"The {planet1}-{planet2} {aspect} suggests that your {planet_influences.get(planet1, 'energy')} {aspect_influences.get(aspect, 'connects with')} your {planet_influences.get(planet2, 'energy')}.",
        f"This {aspect} between {planet1} and {planet2} indicates that issues of {planet_influences.get(planet1, 'energy')} are significantly connected to {planet_influences.get(planet2, 'energy')} in your chart."
    ]
    
    return random.choice(descriptions)

def generate_lucky_time(zodiac_sign: str, prediction_date: date) -> str:
    """Generate a lucky time of day with proper from-to format"""
    random.seed(f"{zodiac_sign}_{prediction_date}")
    
    # Define time periods with proper hour ranges
    time_ranges = [
        ("6:00 AM", "8:00 AM"),
        ("8:00 AM", "10:00 AM"),
        ("10:00 AM", "12:00 PM"),
        ("12:00 PM", "2:00 PM"),
        ("2:00 PM", "4:00 PM"),
        ("4:00 PM", "6:00 PM"),
        ("6:00 PM", "8:00 PM"),
        ("8:00 PM", "10:00 PM"),
        ("10:00 PM", "12:00 AM")
    ]
    
    # Select a random time range
    start_time, end_time = random.choice(time_ranges)
    
    return f"{start_time} to {end_time}"

def generate_description(section: str, zodiac_sign: str, prediction_type: str, 
                        planetary_positions: Dict[str, Dict[str, Any]],
                        aspects: List[Dict[str, Any]], 
                        language: str = "English") -> str:
    """Generate a detailed, specific, and realistic description for a horoscope category"""
    
    # Seed based on all parameters to ensure variability but consistency for same inputs
    seed_value = f"{zodiac_sign}_{section}_{prediction_type}_{date.today()}"
    random.seed(seed_value)
    
    # Get ruling planet and element for zodiac sign for more personalized predictions
    ruling_planet = RULING_PLANETS.get(zodiac_sign, "Sun")
    element = ZODIAC_ELEMENTS.get(zodiac_sign, "Fire")
    
    # Get timeframe-specific language
    timeframe_phrases = {
        "daily": ["today", "this day", "the hours ahead", "by the end of the day"],
        "weekly": ["this week", "over the coming days", "in the days ahead", "by the end of the week"],
        "monthly": ["this month", "in the weeks ahead", "throughout this lunar cycle", "as the month progresses"],
        "yearly": ["this year", "in the months ahead", "throughout the coming seasons", "as the year unfolds"]
    }
    
    # Hindi timeframe phrases
    hindi_timeframe_phrases = {
        "daily": ["आज", "इस दिन", "आने वाले घंटों में", "दिन के अंत तक"],
        "weekly": ["इस सप्ताह", "आने वाले दिनों में", "आगामी दिनों में", "सप्ताह के अंत तक"],
        "monthly": ["इस महीने", "आने वाले हफ्तों में", "इस चंद्र चक्र के दौरान", "जैसे-जैसे महीना आगे बढ़ता है"],
        "yearly": ["इस वर्ष", "आने वाले महीनों में", "आने वाले मौसमों में", "जैसे-जैसे वर्ष आगे बढ़ता है"]
    }
    
    # Gujarati timeframe phrases
    gujarati_timeframe_phrases = {
        "daily": ["આજે", "આ દિવસે", "આવનારા કલાકોમાં", "દિવસના અંત સુધીમાં"],
        "weekly": ["આ અઠવાડિયે", "આવનારા દિવસોમાં", "આગામી દિવસોમાં", "અઠવાડિયાના અંત સુધીમાં"],
        "monthly": ["આ મહિને", "આવનારા અઠવાડિયામાં", "આ ચંદ્ર ચક્ર દરમિયાન", "જેમ જેમ મહિનો આગળ વધે છે"],
        "yearly": ["આ વર્ષે", "આવનારા મહિનાઓમાં", "આવનારી ઋતુઓમાં", "જેમ જેમ વર્ષ આગળ વધે છે"]
    }
    
    # Select appropriate timeframe phrases based on language
    if language.lower() == "hindi":
        selected_timeframe_phrases = hindi_timeframe_phrases
    elif language.lower() == "gujarati":
        selected_timeframe_phrases = gujarati_timeframe_phrases
    else:
        selected_timeframe_phrases = timeframe_phrases
    
    timeframe = prediction_type.lower()
    timeframe_phrase = random.choice(selected_timeframe_phrases.get(timeframe, selected_timeframe_phrases["daily"]))
    
    # Get significant planet and its info
    if planetary_positions and len(planetary_positions) > 0:
        significant_planet = random.choice(list(planetary_positions.keys()))
        planet_info = planetary_positions.get(significant_planet, {})
    else:
        significant_planet = ruling_planet
        planet_info = {}
    
    planet_sign = planet_info.get("sign", "Aries")
    
    # Retrograde text based on language
    if language.lower() == "english":
        planet_retrograde = " in retrograde motion" if random.random() < 0.1 else ""
    elif language.lower() == "hindi":
        planet_retrograde = " वक्री गति में" if random.random() < 0.1 else ""
    elif language.lower() == "gujarati":
        planet_retrograde = " વક્રી ગતિમાં" if random.random() < 0.1 else ""
    else:
        planet_retrograde = " in retrograde motion" if random.random() < 0.1 else ""
    
    # Base variables that work for all sections
    variables = {
        "significant_planet": significant_planet,
        "planet_sign": planet_sign,
        "planet_retrograde": planet_retrograde,
        "zodiac_sign": zodiac_sign,
        "timeframe": timeframe_phrase,
        "timeframe_cap": timeframe_phrase.capitalize() if language.lower() == "english" else timeframe_phrase,
        "ruling_planet": ruling_planet,
        "element": element,
        "house": random.choice(["first", "second", "third", "fourth", "fifth", "sixth", 
                               "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth"]),
        "general_energy": random.choice(["transformative", "clarifying", "harmonizing", "energizing", 
                                        "stabilizing", "expansive", "reflective", "dynamic"])
    }

    # If language is Hindi or Gujarati, translate the base variables
    if language.lower() in ["hindi", "gujarati"]:
        # Use translation mapping from HOROSCOPE_TRANSLATIONS
        translations = HOROSCOPE_TRANSLATIONS.get(language.lower(), {})
        for key in ["significant_planet", "planet_sign", "zodiac_sign", "ruling_planet", 
                   "element", "house", "general_energy"]:
            if variables[key] in translations:
                variables[key] = translations[variables[key]]

    try:
        if section == "Career":
            # ENGLISH TEMPLATES
            templates = [
                "Professional matters receive {career_energy} attention {timeframe} as {significant_planet} moves through {planet_sign}{planet_retrograde}. This planetary influence highlights your approach to {career_focus}, suggesting opportunities for {career_opportunity}. Pay attention to {work_dynamic} that may shift your perspective on {professional_aspect}. A situation involving {career_situation} calls for {professional_approach}, especially when dealing with {workplace_element}. Your natural strengths in {career_strength} serve you well, while being mindful of {career_challenge} helps you navigate changing circumstances effectively."
            ]
            
            # HINDI TEMPLATES
            hindi_templates = [
                "{timeframe} पेशेवर मामलों पर {career_energy} ध्यान मिलेगा क्योंकि {significant_planet} {planet_sign} से गुजर रहा है{planet_retrograde}। यह ग्रह प्रभाव आपके {career_focus} के दृष्टिकोण पर प्रकाश डालता है, जिससे {career_opportunity} के अवसर मिलते हैं। {work_dynamic} पर ध्यान दें जो {professional_aspect} पर आपके दृष्टिकोण को बदल सकता है। {career_situation} से जुड़ी स्थिति के लिए {professional_approach} की आवश्यकता होती है, विशेष रूप से {workplace_element} से निपटते समय। {career_strength} में आपकी प्राकृतिक ताकत आपके लिए अच्छी तरह से काम करती है, जबकि {career_challenge} का ध्यान रखना आपको बदलती परिस्थितियों में कुशलता से आगे बढ़ने में मदद करता है।"
            ]
            
            # GUJARATI TEMPLATES
            gujarati_templates = [
                "{timeframe} વ્યાવસાયિક બાબતોને {career_energy} ધ્યાન મળશે કારણ કે {significant_planet} {planet_sign}માંથી પસાર થઈ રહ્યો છે{planet_retrograde}. આ ગ્રહનો પ્રભાવ તમારા {career_focus}ના અભિગમને પ્રકાશિત કરે છે, જે {career_opportunity}ની તકો સૂચવે છે. {work_dynamic} પર ધ્યાન આપો જે {professional_aspect} પરના તમારા દ્રષ્ટિકોણને બદલી શકે છે. {career_situation}ને લગતી પરિસ્થિતિ માટે {professional_approach}ની જરૂર છે, ખાસ કરીને {workplace_element} સાથે વ્યવહાર કરતી વખતે. {career_strength}માં તમારી કુદરતી શક્તિઓ તમને સારી રીતે કામ આપે છે, જ્યારે {career_challenge}ને ધ્યાનમાં રાખવાથી તમને બદલાતી પરિસ્થિતિઓમાં કુશળતાથી આગળ વધવામાં મદદ મળે છે."
            ]
            
            # ENGLISH VARIABLES
            career_variables = {
                "career_energy": random.choice(["focused", "dynamic", "strategic", "innovative", "balanced", "determined", "insightful"]),
                "career_focus": random.choice(["leadership abilities", "collaborative skills", "technical expertise", "creative expression", "problem-solving capabilities", "communication strengths", "strategic thinking"]),
                "career_opportunity": random.choice(["advancement through merit", "skill development", "networking expansion", "project leadership", "creative contributions", "problem resolution", "strategic input"]),
                "work_dynamic": random.choice(["team interactions", "project developments", "communication patterns", "resource allocations", "timeline adjustments", "responsibility shifts", "collaborative opportunities"]),
                "professional_aspect": random.choice(["work-life balance", "career trajectory", "skill utilization", "team dynamics", "project management", "professional relationships", "goal achievement"]),
                "career_situation": random.choice(["unexpected opportunity", "resource allocation", "team restructuring", "project timeline", "skill assessment", "performance review", "collaborative venture"]),
                "professional_approach": random.choice(["balanced consideration", "strategic planning", "clear communication", "collaborative effort", "systematic organization", "innovative thinking", "patient persistence"]),
                "workplace_element": random.choice(["competing priorities", "team dynamics", "resource constraints", "timeline pressures", "changing requirements", "communication challenges", "technology adaptations"]),
                "career_strength": random.choice(["analytical thinking", "creative problem-solving", "team collaboration", "detail orientation", "strategic planning", "adaptability", "communication skills"]),
                "career_challenge": random.choice(["perfectionist tendencies", "overcommitment", "communication assumptions", "impatience with process", "resistance to change", "delegation difficulties", "work-life boundaries"])
            }
            
            # HINDI VARIABLES
            hindi_career_variables = {
                "career_energy": random.choice(["केंद्रित", "गतिशील", "रणनीतिक", "नवीन", "संतुलित", "दृढ़", "अंतर्दृष्टिपूर्ण"]),
                "career_focus": random.choice(["नेतृत्व क्षमताओं", "सहयोगी कौशल", "तकनीकी विशेषज्ञता", "रचनात्मक अभिव्यक्ति", "समस्या-समाधान क्षमताओं", "संचार शक्तियों", "रणनीतिक सोच"]),
                "career_opportunity": random.choice(["योग्यता के माध्यम से प्रगति", "कौशल विकास", "नेटवर्किंग विस्तार", "परियोजना नेतृत्व", "रचनात्मक योगदान", "समस्या समाधान", "रणनीतिक इनपुट"]),
                "work_dynamic": random.choice(["टीम इंटरैक्शन", "परियोजना विकास", "संचार पैटर्न", "संसाधन आवंटन", "समयरेखा समायोजन", "जिम्मेदारी बदलाव", "सहयोगात्मक अवसर"]),
                "professional_aspect": random.choice(["काम-जीवन संतुलन", "करियर प्रक्षेपवक्र", "कौशल उपयोग", "टीम गतिशीलता", "परियोजना प्रबंधन", "पेशेवर संबंध", "लक्ष्य प्राप्ति"]),
                "career_situation": random.choice(["अप्रत्याशित अवसर", "संसाधन आवंटन", "टीम पुनर्गठन", "परियोजना समयरेखा", "कौशल मूल्यांकन", "प्रदर्शन समीक्षा", "सहयोगी उद्यम"]),
                "professional_approach": random.choice(["संतुलित विचार", "रणनीतिक योजना", "स्पष्ट संचार", "सहयोगी प्रयास", "व्यवस्थित संगठन", "नवीन सोच", "धैर्यपूर्ण दृढ़ता"]),
                "workplace_element": random.choice(["प्रतिस्पर्धी प्राथमिकताएं", "टीम गतिशीलता", "संसाधन बाधाएं", "समयरेखा दबाव", "बदलती आवश्यकताएं", "संचार चुनौतियां", "प्रौद्योगिकी अनुकूलन"]),
                "career_strength": random.choice(["विश्लेषणात्मक सोच", "रचनात्मक समस्या-समाधान", "टीम सहयोग", "विवरण उन्मुखता", "रणनीतिक योजना", "अनुकूलनशीलता", "संचार कौशल"]),
                "career_challenge": random.choice(["पूर्णतावादी प्रवृत्तियां", "अधिक प्रतिबद्धता", "संचार मान्यताएं", "प्रक्रिया के साथ अधीरता", "परिवर्तन का विरोध", "प्रतिनिधिमंडल की कठिनाइयां", "कार्य-जीवन सीमाएं"])
            }
            
            # GUJARATI VARIABLES
            gujarati_career_variables = {
                "career_energy": random.choice(["કેન્દ્રિત", "ગતિશીલ", "વ્યૂહાત્મક", "નવીન", "સંતુલિત", "દૃઢ", "અંતર્દૃષ્ટિપૂર્ણ"]),
                "career_focus": random.choice(["નેતૃત્વ ક્ષમતાઓ", "સહયોગી કૌશલ્યો", "ટેકનિકલ નિપુણતા", "સર્જનાત્મક અભિવ્યક્તિ", "સમસ્યા-ઉકેલ ક્ષમતાઓ", "સંદેશાવ્યવહારની શક્તિઓ", "વ્યૂહાત્મક વિચારધારા"]),
                "career_opportunity": random.choice(["યોગ્યતા દ્વારા પ્રગતિ", "કૌશલ્ય વિકાસ", "નેટવર્કિંગ વિસ્તરણ", "પ્રોજેક્ટ નેતૃત્વ", "સર્જનાત્મક યોગદાન", "સમસ્યા ઉકેલ", "વ્યૂહાત્મક ઇનપુટ"]),
                "work_dynamic": random.choice(["ટીમ ઇન્ટરેક્શન", "પ્રોજેક્ટ વિકાસ", "સંદેશાવ્યવહાર પેટર્ન", "સંસાધન ફાળવણી", "સમયમર્યાદા સમાયોજન", "જવાબદારી શિફ્ટ", "સહયોગી તકો"]),
                "professional_aspect": random.choice(["કામ-જીવન સંતુલન", "કારકિર્દી માર્ગ", "કૌશલ્ય ઉપયોગ", "ટીમ ડાયનેમિક્સ", "પ્રોજેક્ટ મેનેજમેન્ટ", "વ્યાવસાયિક સંબંધો", "લક્ષ્ય સિદ્ધિ"]),
                "career_situation": random.choice(["અણધારી તક", "સંસાધન ફાળવણી", "ટીમ પુનર્ગઠન", "પ્રોજેક્ટ સમયમર્યાદા", "કૌશલ્ય મૂલ્યાંકન", "કામગીરી સમીક્ષા", "સહયોગી સાહસ"]),
                "professional_approach": random.choice(["સંતુલિત વિચારણા", "વ્યૂહાત્મક આયોજન", "સ્પષ્ટ સંદેશાવ્યવહાર", "સહયોગી પ્રયાસ", "વ્યવસ્થિત સંગઠન", "નવિનતા વિચારધારા", "ધૈર્યપૂર્ણ દ્રઢતા"]),
                "workplace_element": random.choice(["સ્પર્ધાત્મક પ્રાથમિકતાઓ", "ટીમ ગતિશીલતા", "સંસાધન મર્યાદાઓ", "સમયમર્યાદાનું દબાણ", "બદલાતી જરૂરિયાતો", "સંદેશાવ્યવહાર પડકારો", "ટેકનોલોજી અનુકૂલનો"]),
                "career_strength": random.choice(["વિશ્લેષણાત્મક વિચારધારા", "સર્જનાત્મક સમસ્યા-ઉકેલ", "ટીમ સહયોગ", "વિગતવાર અભિગમ", "વ્યૂહાત્મક આયોજન", "અનુકૂલનશીલતા", "સંદેશાવ્યવહાર કૌશલ્યો"]),
                "career_challenge": random.choice(["પૂર્ણતાવાદી વલણો", "વધુ પડતી પ્રતિબદ્ધતા", "સંદેશાવ્યવહાર ધારણાઓ", "પ્રક્રિયા સાથે અધીરતા", "પરિવર્તનનો પ્રતિકાર", "પ્રતિનિધિમંડળની મુશ્કેલીઓ", "કામ-જીવન સરહદો"])
            }

            # Update variables based on language
            if language.lower() == "hindi":
                variables.update(hindi_career_variables)
                templates = hindi_templates
            elif language.lower() == "gujarati":
                variables.update(gujarati_career_variables)
                templates = gujarati_templates
            else:
                variables.update(career_variables)
                
        elif section == "Love":
            # ENGLISH TEMPLATES
            templates = [
                "Relationships receive {love_energy} attention {timeframe} as {significant_planet} moves through {planet_sign}{planet_retrograde}. This cosmic influence highlights {relationship_aspect}, bringing opportunities for {love_opportunity}. Pay attention to {emotional_pattern} that reveals important insights about {relationship_insight}. A situation involving {love_situation} invites {relationship_approach}, particularly when considering {emotional_need}. Your capacity for {love_strength} shines through, while awareness of {relationship_challenge} helps create more authentic connections."
            ]
            
            # HINDI TEMPLATES
            hindi_templates = [
                "{timeframe} संबंधों को {love_energy} ध्यान मिलेगा क्योंकि {significant_planet} {planet_sign} से गुजर रहा है{planet_retrograde}। यह ब्रह्मांडीय प्रभाव {relationship_aspect} पर प्रकाश डालता है, जिससे {love_opportunity} के अवसर मिलते हैं। {emotional_pattern} पर ध्यान दें जो {relationship_insight} के बारे में महत्वपूर्ण जानकारी देता है। {love_situation} से जुड़ी स्थिति {relationship_approach} को आमंत्रित करती है, विशेष रूप से {emotional_need} पर विचार करते समय। आपकी {love_strength} क्षमता उभरकर सामने आती है, जबकि {relationship_challenge} के बारे में जागरूकता अधिक प्रामाणिक संबंध बनाने में मदद करती है।"
            ]
            
            # GUJARATI TEMPLATES
            gujarati_templates = [
                "{timeframe} સંબંધોને {love_energy} ધ્યાન મળશે કારણ કે {significant_planet} {planet_sign}માંથી પસાર થઈ રહ્યો છે{planet_retrograde}. આ બ્રહ્માંડીય પ્રભાવ {relationship_aspect}ને પ્રકાશિત કરે છે, જે {love_opportunity}ની તકો લાવે છે. {emotional_pattern} પર ધ્યાન આપો જે {relationship_insight} વિશે મહત્વપૂર્ણ અંતર્દૃષ્ટિ આપે છે. {love_situation}ને લગતી પરિસ્થિતિ {relationship_approach}ને આમંત્રિત કરે છે, ખાસ કરીને {emotional_need}ને ધ્યાનમાં રાખતા. તમારી {love_strength} ક્ષમતા ઉજાગર થાય છે, જ્યારે {relationship_challenge}ની જાગૃતિ વધુ પ્રામાણિક જોડાણો બનાવવામાં મદદ કરે છે."
            ]
            
            # ENGLISH VARIABLES
            love_variables = {
                "love_energy": random.choice(["gentle", "passionate", "harmonizing", "deepening", "clarifying", "healing", "transformative"]),
                "relationship_aspect": random.choice(["emotional communication", "intimacy levels", "shared values", "future planning", "conflict resolution", "affection expression", "trust building"]),
                "love_opportunity": random.choice(["deeper understanding", "emotional healing", "renewed connection", "honest communication", "shared experiences", "intimate moments", "relationship growth"]),
                "emotional_pattern": random.choice(["communication styles", "affection needs", "conflict responses", "intimacy preferences", "trust expressions", "emotional timing", "love languages"]),
                "relationship_insight": random.choice(["authentic emotional needs", "communication preferences", "love expression styles", "relationship priorities", "emotional boundaries", "intimacy requirements", "partnership dynamics"]),
                "love_situation": random.choice(["misunderstanding", "emotional distance", "timing mismatch", "communication gap", "different priorities", "past influence", "external pressure"]),
                "relationship_approach": random.choice(["gentle patience", "honest communication", "emotional availability", "mutual understanding", "shared vulnerability", "respectful dialogue", "compassionate listening"]),
                "emotional_need": random.choice(["security and stability", "adventure and growth", "communication and understanding", "independence and togetherness", "passion and companionship", "trust and loyalty", "creativity and fun"]),
                "love_strength": random.choice(["emotional empathy", "loyal commitment", "passionate expression", "patient understanding", "honest communication", "playful affection", "supportive presence"]),
                "relationship_challenge": random.choice(["emotional assumptions", "communication timing", "independence needs", "perfectionist expectations", "past influences", "vulnerability fears", "control tendencies"])
            }
            
            # HINDI VARIABLES
            hindi_love_variables = {
                "love_energy": random.choice(["कोमल", "जोशीला", "सामंजस्यपूर्ण", "गहन", "स्पष्ट", "उपचारात्मक", "परिवर्तनकारी"]),
                "relationship_aspect": random.choice(["भावनात्मक संचार", "निकटता के स्तर", "साझा मूल्य", "भविष्य की योजना", "संघर्ष समाधान", "स्नेह अभिव्यक्ति", "विश्वास निर्माण"]),
                "love_opportunity": random.choice(["गहरी समझ", "भावनात्मक उपचार", "नवीनीकृत संबंध", "ईमानदार संवाद", "साझा अनुभव", "निकटता के क्षण", "संबंध विकास"]),
                "emotional_pattern": random.choice(["संचार शैली", "स्नेह की जरूरतें", "संघर्ष प्रतिक्रियाएं", "निकटता प्राथमिकताएं", "विश्वास अभिव्यक्तियां", "भावनात्मक समय", "प्रेम भाषाएं"]),
                "relationship_insight": random.choice(["प्रामाणिक भावनात्मक जरूरतें", "संचार प्राथमिकताएं", "प्रेम अभिव्यक्ति शैली", "संबंध प्राथमिकताएं", "भावनात्मक सीमाएं", "निकटता आवश्यकताएं", "साझेदारी गतिशीलता"]),
                "love_situation": random.choice(["गलतफहमी", "भावनात्मक दूरी", "समय बेमेल", "संचार अंतर", "अलग प्राथमिकताएं", "पिछला प्रभाव", "बाहरी दबाव"]),
                "relationship_approach": random.choice(["कोमल धैर्य", "ईमानदार संवाद", "भावनात्मक उपलब्धता", "आपसी समझ", "साझा भेद्यता", "सम्मानजनक संवाद", "करुणामय सुनना"]),
                "emotional_need": random.choice(["सुरक्षा और स्थिरता", "साहसिक और विकास", "संचार और समझ", "स्वतंत्रता और एकजुटता", "जुनून और साथीपन", "विश्वास और वफादारी", "रचनात्मकता और मज़ा"]),
                "love_strength": random.choice(["भावनात्मक सहानुभूति", "वफादार प्रतिबद्धता", "जोशीली अभिव्यक्ति", "धैर्यपूर्ण समझ", "ईमानदार संचार", "मस्तिष्क स्नेह", "सहायक उपस्थिति"]),
                "relationship_challenge": random.choice(["भावनात्मक धारणाएं", "संचार समय", "स्वतंत्रता की जरूरतें", "पूर्णतावादी अपेक्षाएं", "पिछले प्रभाव", "भेद्यता भय", "नियंत्रण प्रवृत्तियां"])
            }
            
            # GUJARATI VARIABLES
            gujarati_love_variables = {
                "love_energy": random.choice(["કોમળ", "ઉત્સાહી", "સુમેળભર્યું", "ઊંડું", "સ્પષ્ટ", "સારવાર", "પરિવર્તનકારક"]),
                "relationship_aspect": random.choice(["ભાવનાત્મક સંદેશાવ્યવહાર", "નિકટતા સ્તરો", "સહભાગી મૂલ્યો", "ભવિષ્યનું આયોજન", "સંઘર્ષ નિરાકરણ", "સ્નેહ અભિવ્યક્તિ", "વિશ્વાસ નિર્માણ"]),
                "love_opportunity": random.choice(["ઊંડી સમજણ", "ભાવનાત્મક સારવાર", "પુનઃજોડાણ", "પ્રામાણિક સંવાદ", "સહભાગી અનુભવો", "નિકટના ક્ષણો", "સંબંધ વિકાસ"]),
                "emotional_pattern": random.choice(["સંદેશાવ્યવહાર શૈલી", "સ્નેહની જરૂરિયાતો", "સંઘર્ષ પ્રતિક્રિયાઓ", "નિકટતા પસંદગીઓ", "વિશ્વાસ અભિવ્યક્તિઓ", "ભાવનાત્મક સમય", "પ્રેમ ભાષાઓ"]),
                "relationship_insight": random.choice(["પ્રામાણિક ભાવનાત્મક જરૂરિયાતો", "સંદેશાવ્યવહાર પસંદગીઓ", "પ્રેમ અભિવ્યક્તિ શૈલીઓ", "સંબંધ પ્રાથમિકતાઓ", "ભાવનાત્મક સીમાઓ", "નિકટતા આવશ્યકતાઓ", "ભાગીદારી ગતિશીલતા"]),
                "love_situation": random.choice(["ગેરસમજ", "ભાવનાત્મક અંતર", "સમય બેમેળ", "સંદેશાવ્યવહાર અંતર", "અલગ પ્રાથમિકતાઓ", "ભૂતકાળનો પ્રભાવ", "બાહ્ય દબાણ"]),
                "relationship_approach": random.choice(["કોમળ ધીરજ", "પ્રામાણિક સંવાદ", "ભાવનાત્મક ઉપલબ્ધતા", "પરસ્પર સમજણ", "સહભાગી નિસ્બત", "આદરપૂર્ણ સંવાદ", "સહાનુભૂતિપૂર્ણ સાંભળવું"]),
                "emotional_need": random.choice(["સુરક્ષા અને સ્થિરતા", "સાહસ અને વિકાસ", "સંદેશાવ્યવહાર અને સમજણ", "સ્વતંત્રતા અને સાથીપણું", "જોશ અને સોબત", "વિશ્વાસ અને વફાદારી", "સર્જનાત્મકતા અને આનંદ"]),
                "love_strength": random.choice(["ભાવનાત્મક સહાનુભૂતિ", "વફાદાર પ્રતિબદ્ધતા", "ઉત્સાહી અભિવ્યક્તિ", "ધીરજપૂર્ણ સમજણ", "પ્રામાણિક સંદેશાવ્યવહાર", "આનંદદાયક સ્નેહ", "સહાયક હાજરી"]),
                "relationship_challenge": random.choice(["ભાવનાત્મક ધારણાઓ", "સંદેશાવ્યવહાર સમય", "સ્વતંત્રતા જરૂરિયાતો", "પૂર્ણતાવાદી અપેક્ષાઓ", "ભૂતકાળના પ્રભાવો", "નબળાઈના ભય", "નિયંત્રણ વલણો"])
            }
            
            # Update variables based on language
            if language.lower() == "hindi":
                variables.update(hindi_love_variables)
                templates = hindi_templates
            elif language.lower() == "gujarati":
                variables.update(gujarati_love_variables)
                templates = gujarati_templates
            else:
                variables.update(love_variables)

        elif section == "Finance":
            # ENGLISH TEMPLATES
            templates = [
                "Financial matters come into sharper focus {timeframe} as {significant_planet} travels through {planet_sign}{planet_retrograde}. This cosmic influence highlights {financial_area}, suggesting it's a {timing_quality} time to {financial_action}. Pay particular attention to {money_opportunity} that may emerge through {opportunity_source}. A situation involving {financial_situation} calls for {financial_approach}, especially regarding {resource_aspect}. Your natural strengths in {financial_strength} serve you well now, though be mindful of tendencies toward {financial_weakness} when making decisions about {specific_financial_matter}."
            ]
            
            # HINDI TEMPLATES
            hindi_templates = [
                "{timeframe} वित्तीय मामले अधिक स्पष्ट होंगे क्योंकि {significant_planet} {planet_sign} से गुजर रहा है{planet_retrograde}। यह ब्रह्मांडीय प्रभाव {financial_area} पर प्रकाश डालता है, जिससे यह सुझाव मिलता है कि यह {financial_action} के लिए {timing_quality} समय है। {opportunity_source} के माध्यम से उभरने वाले {money_opportunity} पर विशेष ध्यान दें। {financial_situation} से जुड़ी स्थिति के लिए {financial_approach} की आवश्यकता होती है, खासकर {resource_aspect} के संबंध में। {financial_strength} में आपकी प्राकृतिक शक्तियां अभी आपके लिए अच्छी तरह से काम करती हैं, हालांकि {specific_financial_matter} के बारे में निर्णय लेते समय {financial_weakness} की प्रवृत्तियों के प्रति सावधान रहें।"
            ]
            
            # GUJARATI TEMPLATES
            gujarati_templates = [
                "{timeframe} નાણાકીય બાબતો વધુ સ્પષ્ટ ફોકસમાં આવશે કારણ કે {significant_planet} {planet_sign}માંથી પસાર થઈ રહ્યો છે{planet_retrograde}. આ બ્રહ્માંડીય પ્રભાવ {financial_area}ને પ્રકાશિત કરે છે, જે સૂચવે છે કે આ {financial_action} માટે {timing_quality} સમય છે. {opportunity_source} દ્વારા ઉભરી શકે તેવા {money_opportunity} પર વિશેષ ધ્યાન આપો. {financial_situation}ને લગતી પરિસ્થિતિ માટે {financial_approach}ની જરૂર છે, ખાસ કરીને {resource_aspect}ના સંદર્ભમાં. {financial_strength}માં તમારી કુદરતી શક્તિઓ હવે તમને સારી રીતે કામ આપે છે, જોકે {specific_financial_matter} વિશે નિર્ણયો લેતી વખતે {financial_weakness} તરફના વલણો વિશે સાવધ રહો."
            ]
            
            # ENGLISH VARIABLES
            finance_variables = {
                "financial_area": random.choice(["income opportunities", "spending patterns", "savings strategies", "investment approaches", "debt management", "resource allocation", "long-term financial planning"]),
                "timing_quality": random.choice(["strategic", "opportune", "reflective", "clarifying", "evaluative", "productive", "insightful"]),
                "financial_action": random.choice(["review your budget with fresh eyes", "reevaluate recurring expenses", "research investment opportunities", "discuss financial goals with advisors", "automate savings processes", "consolidate or refinance existing obligations", "update your financial protection measures"]),
                "money_opportunity": random.choice(["potential income streams", "cost-saving measures", "investment possibilities", "refinancing options", "resource optimization", "valuable partnerships", "efficiency improvements"]),
                "opportunity_source": random.choice(["professional connections", "overlooked resources", "market shifts", "technological tools", "specialized knowledge", "timing advantages", "collaborative ventures"]),
                "financial_situation": random.choice(["unexpected expenses", "resource allocation decisions", "investment timing", "income fluctuations", "savings priorities", "debt management", "financial partnerships"]),
                "financial_approach": random.choice(["methodical analysis", "balanced evaluation", "strategic patience", "proactive planning", "careful documentation", "informed consultation", "systematic review"]),
                "resource_aspect": random.choice(["long-term security", "immediate liquidity needs", "growth potential", "risk management", "tax implications", "estate considerations", "lifestyle alignment"]),
                "financial_strength": random.choice(["analytical thinking", "patient strategy", "consistent habits", "research abilities", "disciplined approach", "clear prioritization", "balanced perspective"]),
                "financial_weakness": random.choice(["emotional decision-making", "short-term thinking", "analysis paralysis", "risk aversion", "impulsive actions", "procrastination", "information overload"]),
                "specific_financial_matter": random.choice(["major purchases", "investment allocations", "savings strategies", "debt management", "income opportunities", "insurance coverage", "tax planning"])
            }
            
            # HINDI VARIABLES
            hindi_finance_variables = {
                "financial_area": random.choice(["आय के अवसर", "खर्च के पैटर्न", "बचत रणनीतियां", "निवेश दृष्टिकोण", "ऋण प्रबंधन", "संसाधन आवंटन", "दीर्घकालिक वित्तीय योजना"]),
                "timing_quality": random.choice(["रणनीतिक", "अनुकूल", "चिंतनशील", "स्पष्ट करने वाला", "मूल्यांकनात्मक", "उत्पादक", "अंतर्दृष्टिपूर्ण"]),
                "financial_action": random.choice(["नई नजर से अपने बजट की समीक्षा करें", "आवर्ती खर्चों का पुनर्मूल्यांकन करें", "निवेश के अवसरों पर शोध करें", "सलाहकारों के साथ वित्तीय लक्ष्यों पर चर्चा करें", "बचत प्रक्रियाओं को स्वचालित करें", "मौजूदा दायित्वों को समेकित या पुनर्वित्त करें", "अपने वित्तीय सुरक्षा उपायों को अपडेट करें"]),
                "money_opportunity": random.choice(["संभावित आय स्रोत", "लागत बचत उपाय", "निवेश संभावनाएं", "पुनर्वित्त विकल्प", "संसाधन अनुकूलन", "मूल्यवान साझेदारी", "दक्षता सुधार"]),
                "opportunity_source": random.choice(["पेशेवर संबंध", "अनदेखे संसाधन", "बाजार परिवर्तन", "तकनीकी उपकरण", "विशिष्ट ज्ञान", "समय का लाभ", "सहयोगी उद्यम"]),
                "financial_situation": random.choice(["अप्रत्याशित खर्च", "संसाधन आवंटन निर्णय", "निवेश का समय", "आय में उतार-चढ़ाव", "बचत प्राथमिकताएं", "ऋण प्रबंधन", "वित्तीय साझेदारी"]),
                "financial_approach": random.choice(["पद्धतिगत विश्लेषण", "संतुलित मूल्यांकन", "रणनीतिक धैर्य", "सक्रिय योजना", "सावधानीपूर्ण दस्तावेज़ीकरण", "सूचित परामर्श", "व्यवस्थित समीक्षा"]),
                "resource_aspect": random.choice(["दीर्घकालिक सुरक्षा", "तत्काल तरलता की जरूरतें", "विकास क्षमता", "जोखिम प्रबंधन", "कर प्रभाव", "संपत्ति विचार", "जीवनशैली संरेखण"]),
                "financial_strength": random.choice(["विश्लेषणात्मक सोच", "धैर्यपूर्ण रणनीति", "निरंतर आदतें", "अनुसंधान क्षमताएं", "अनुशासित दृष्टिकोण", "स्पष्ट प्राथमिकता", "संतुलित दृष्टिकोण"]),
                "financial_weakness": random.choice(["भावनात्मक निर्णय लेना", "अल्पकालिक सोच", "विश्लेषण पक्षाघात", "जोखिम से बचना", "आवेगी कार्य", "टालमटोल", "सूचना अधिभार"]),
                "specific_financial_matter": random.choice(["बड़ी खरीदारी", "निवेश आवंटन", "बचत रणनीतियां", "ऋण प्रबंधन", "आय के अवसर", "बीमा कवरेज", "कर नियोजन"])
            }
            
            # GUJARATI VARIABLES
            gujarati_finance_variables = {
                "financial_area": random.choice(["આવકની તકો", "ખર્ચની પેટર્ન", "બચતની વ્યૂહરચનાઓ", "રોકાણ અભિગમો", "દેવું વ્યવસ્થાપન", "સંસાધન ફાળવણી", "લાંબા ગાળાનું નાણાકીય આયોજન"]),
                "timing_quality": random.choice(["વ્યૂહાત્મક", "અનુકૂળ", "ચિંતનશીલ", "સ્પષ્ટ કરનાર", "મૂલ્યાંકન", "ઉત્પાદક", "અંતર્દૃષ્ટિપૂર્ણ"]),
                "financial_action": random.choice(["તાજી નજરથી તમારા બજેટની સમીક્ષા કરો", "નિયમિત ખર્ચોનું પુનઃમૂલ્યાંકન કરો", "રોકાણની તકો પર સંશોધન કરો", "સલાહકારો સાથે નાણાકીય લક્ષ્યો પર ચર્ચા કરો", "બચત પ્રક્રિયાઓને ઑટોમેટ કરો", "હાલના દેવાને એકત્રિત કરો અથવા રિફાઇનાન્સ કરો", "તમારા નાણાકીય સુરક્ષા પગલાંઓને અપડેટ કરો"]),
                "money_opportunity": random.choice(["સંભવિત આવક સ્ત્રોતો", "ખર્ચ બચાવવાના પગલાં", "રોકાણની સંભાવનાઓ", "રિફાઇનાન્સિંગ વિકલ્પો", "સંસાધન ઓપ્ટિમાઈઝેશન", "મૂલ્યવાન ભાગીદારી", "કાર્યક્ષમતા સુધારણા"]),
                "opportunity_source": random.choice(["વ્યાવસાયિક જોડાણો", "અવગણવામાં આવેલ સ્ત્રોતો", "બજાર શિફ્ટ", "ટેકનોલોજીકલ ટૂલ્સ", "વિશેષ જ્ઞાન", "સમયના ફાયદા", "સહયોગી સાહસો"]),
                "financial_situation": random.choice(["અનપેક્ષિત ખર્ચ", "સંસાધન ફાળવણી નિર્ણયો", "રોકાણનો સમય", "આવકમાં ચઢાવ-ઉતાર", "બચત પ્રાથમિકતાઓ", "દેવાનું વ્યવસ્થાપન", "નાણાકીય ભાગીદારી"]),
                "financial_approach": random.choice(["પદ્ધતિસરનું વિશ્લેષણ", "સંતુલિત મૂલ્યાંકન", "વ્યૂહાત્મક ધીરજ", "સક્રિય આયોજન", "કાળજીપૂર્વક દસ્તાવેજીકરણ", "સૂચિત પરામર્શ", "પદ્ધતિસરની સમીક્ષા"]),
                "resource_aspect": random.choice(["લાંબા ગાળાની સુરક્ષા", "તાત્કાલિક તરલતાની જરૂરિયાતો", "વિકાસ સંભાવના", "જોખમ વ્યવસ્થાપન", "કર અસરો", "સંપત્તિ વિચારણા", "જીવનશૈલી સંરેખણ"]),
                "financial_strength": random.choice(["વિશ્લેષણાત્મક વિચારધારા", "ધીરજપૂર્ણ વ્યૂહરચના", "સાતત્યપૂર્ણ આદતો", "સંશોધન ક્ષમતાઓ", "શિસ્તબદ્ધ અભિગમ", "સ્પષ્ટ પ્રાથમિકતા", "સંતુલિત દ્રષ્ટિકોણ"]),
                "financial_weakness": random.choice(["ભાવનાત્મક નિર્ણય લેવો", "ટૂંકા ગાળાનું વિચારવું", "વિશ્લેષણ લકવો", "જોખમ ટાળવું", "આવેશમાં આવી જવું", "ઢીલ કરવી", "માહિતી અતિભાર"]),
                "specific_financial_matter": random.choice(["મોટી ખરીદી", "રોકાણ ફાળવણી", "બચતની વ્યૂહરચના", "દેવાનું વ્યવસ્થાપન", "આવકની તકો", "વીમા કવરેજ", "કર આયોજન"])
            }
            
            # Update variables based on language
            if language.lower() == "hindi":
                variables.update(hindi_finance_variables)
                templates = hindi_templates
            elif language.lower() == "gujarati":
                variables.update(gujarati_finance_variables)
                templates = gujarati_templates
            else:
                variables.update(finance_variables)
        
        elif section == "Health":
            # English templates
            templates = [
                "Your wellbeing patterns receive {health_energy} {timeframe} as {significant_planet} moves through {planet_sign}{planet_retrograde}. This cosmic influence particularly affects your {body_area}, suggesting benefits from {health_practice}. Pay attention to how {physical_pattern} relates to {energy_impact} – this connection offers valuable insight for {wellness_goal}. {diet_aspect} deserves special consideration, while {movement_approach} could address {specific_concern}. Listen carefully to your body's signals regarding {body_message}, as they contain wisdom about {health_insight}."
            ]
            
            # Hindi templates
            hindi_templates = [
                "आपके स्वास्थ्य पैटर्न {timeframe} {health_energy} प्राप्त करते हैं क्योंकि {significant_planet} {planet_sign} से गुजरता है{planet_retrograde}। यह ब्रह्मांडीय प्रभाव विशेष रूप से आपके {body_area} को प्रभावित करता है, जिससे {health_practice} से लाभ मिलने का संकेत मिलता है। ध्यान दें कि कैसे {physical_pattern} का {energy_impact} से संबंध है - यह कनेक्शन {wellness_goal} के लिए मूल्यवान अंतर्दृष्टि प्रदान करता है। {diet_aspect} विशेष ध्यान देने योग्य है, जबकि {movement_approach} {specific_concern} को संबोधित कर सकता है। {body_message} के संबंध में अपने शरीर के संकेतों को ध्यान से सुनें, क्योंकि वे {health_insight} के बारे में ज्ञान रखते हैं।"
            ]
            
            # Gujarati templates
            gujarati_templates = [
                "તમારી સ્વાસ્થ્યની પેટર્ન {timeframe} {health_energy} મેળવે છે કારણ કે {significant_planet} {planet_sign}માંથી પસાર થાય છે{planet_retrograde}. આ બ્રહ્માંડીય પ્રભાવ ખાસ કરીને તમારા {body_area}ને અસર કરે છે, જે {health_practice}થી લાભ મળવાનું સૂચવે છે. {physical_pattern} કેવી રીતે {energy_impact} સાથે સંબંધિત છે તે પર ધ્યાન આપો - આ જોડાણ {wellness_goal} માટે મૂલ્યવાન અંતર્દૃષ્ટિ આપે છે. {diet_aspect} વિશેષ ધ્યાન આપવાની જરૂર છે, જ્યારે {movement_approach} {specific_concern}ને સંબોધી શકે છે. {body_message} અંગે તમારા શરીરના સંકેતોને કાળજીપૂર્વક સાંભળો, કારણ કે તેમાં {health_insight} વિશે જ્ઞાન સમાયેલું છે."
            ]

            # English variables
            health_variables = {
                "health_energy": random.choice(["renewed awareness", "heightened sensitivity", "balancing influence", "restorative focus", "energetic clarity", "gentle healing", "rhythmic stabilization"]),
                "body_area": random.choice(["nervous system and stress responses", "digestive function and nutrient absorption", "musculoskeletal alignment and flexibility", "cardiovascular health and circulation", "respiratory capacity and oxygen exchange", "immune function and resilience", "hormonal balance and regulation"]),
                "health_practice": random.choice(["establishing consistent sleep patterns", "integrating mindfulness into daily activities", "ensuring proper hydration throughout the day", "incorporating gentle movement between periods of stillness", "supporting digestive health through mindful eating", "creating boundaries around digital exposure", "connecting with nature regularly"]),
                "physical_pattern": random.choice(["energy fluctuations throughout the day", "quality of sleep and wakefulness", "hunger and satiety signals", "body tension and relaxation cycles", "hydration status and effects", "responses to different foods", "recovery time after exertion"]),
                "energy_impact": random.choice(["mental clarity and focus", "emotional resilience", "physical stamina", "immune responsiveness", "stress management capacity", "creative flow", "intuitive awareness"]),
                "wellness_goal": random.choice(["sustainable energy throughout the day", "improved recovery and resilience", "balanced mood and emotional wellbeing", "enhanced mental clarity and focus", "strengthened immunity and reduced inflammation", "better quality rest and restoration", "greater physical comfort and mobility"]),
                "diet_aspect": random.choice(["timing of meals in relation to your body's rhythms", "balance of macronutrients for your specific needs", "hydration practices throughout the day", "nutrient density of food choices", "mindfulness during eating experiences", "potential sensitivities or intolerances", "variety and diversity of food sources"]),
                "movement_approach": random.choice(["consistent gentle movement throughout the day", "strength training appropriate for your body", "flexibility and mobility practices", "balance and coordination activities", "cardiovascular conditioning", "restorative movement and deep relaxation", "nature-based physical activity"]),
                "specific_concern": random.choice(["tension patterns in the upper body", "digestive discomfort after certain meals", "energy fluctuations throughout the day", "sleep quality and restoration", "recovery time after exertion", "mental focus during important tasks", "stress responses to daily challenges"]),
                "body_message": random.choice(["subtle energy shifts after specific activities", "digestive responses to different foods", "patterns of tension or discomfort", "quality of sleep and waking energy", "mental clarity in relation to routines", "emotional states connected to physical sensations", "intuitive pulls toward certain practices"]),
                "health_insight": random.choice(["personal rhythms and optimal timing", "unique nutritional needs", "most effective forms of movement", "ideal balance of activity and rest", "environmental factors affecting wellbeing", "mind-body connections influencing health", "preventative practices for long-term vitality"])
            }
            
            # Hindi variables
            hindi_health_variables = {
                "health_energy": random.choice(["नवीनीकृत जागरूकता", "बढ़ी हुई संवेदनशीलता", "संतुलित प्रभाव", "पुनर्स्थापित फोकस", "ऊर्जावान स्पष्टता", "सौम्य उपचार", "लयबद्ध स्थिरीकरण"]),
                "body_area": random.choice(["तंत्रिका तंत्र और तनाव प्रतिक्रियाओं", "पाचन क्रिया और पोषक तत्त्व अवशोषण", "मांसपेशियों और हड्डियों के संरेखण और लचीलेपन", "हृदय स्वास्थ्य और रक्त संचार", "श्वसन क्षमता और ऑक्सीजन विनिमय", "प्रतिरक्षा प्रणाली और लचीलापन", "हार्मोनल संतुलन और नियमन"]),
                "health_practice": random.choice(["निरंतर नींद पैटर्न स्थापित करना", "दैनिक गतिविधियों में माइंडफुलनेस को एकीकृत करना", "दिन भर उचित हाइड्रेशन सुनिश्चित करना", "स्थिरता के दौरान के बीच हल्की गतिविधि शामिल करना", "सचेत खान-पान के माध्यम से पाचन स्वास्थ्य का समर्थन करना", "डिजिटल एक्सपोजर के चारों ओर सीमाएँ बनाना", "नियमित रूप से प्रकृति से जुड़ना"]),
                "physical_pattern": random.choice(["दिन भर ऊर्जा में उतार-चढ़ाव", "नींद और जागरूकता की गुणवत्ता", "भूख और संतृप्ति के संकेत", "शारीरिक तनाव और आराम के चक्र", "हाइड्रेशन स्थिति और प्रभाव", "विभिन्न खाद्य पदार्थों के प्रति प्रतिक्रिया", "प्रयास के बाद रिकवरी का समय"]),
                "energy_impact": random.choice(["मानसिक स्पष्टता और फोकस", "भावनात्मक लचीलापन", "शारीरिक स्टैमिना", "प्रतिरक्षा प्रतिक्रियाशीलता", "तनाव प्रबंधन क्षमता", "रचनात्मक प्रवाह", "अंतर्ज्ञानात्मक जागरूकता"]),
                "wellness_goal": random.choice(["दिन भर स्थायी ऊर्जा", "बेहतर रिकवरी और लचीलापन", "संतुलित मूड और भावनात्मक कल्याण", "बढ़ा हुआ मानसिक स्पष्टता और फोकस", "मजबूत प्रतिरक्षा प्रणाली और कम सूजन", "बेहतर गुणवत्ता वाला आराम और पुनर्स्थापना", "अधिक शारीरिक आराम और गतिशीलता"]),
                "diet_aspect": random.choice(["आपके शरीर की लय के संबंध में भोजन का समय", "आपकी विशिष्ट जरूरतों के लिए मैक्रोन्यूट्रिएंट्स का संतुलन", "दिन भर हाइड्रेशन प्रथाएं", "भोजन विकल्पों की पोषक तत्व घनत्व", "खाने के अनुभवों के दौरान माइंडफुलनेस", "संभावित संवेदनशीलताएं या असहिष्णुताएं", "भोजन स्रोतों की विविधता और विविधता"]),
                "movement_approach": random.choice(["दिन भर निरंतर हल्की गतिविधि", "आपके शरीर के लिए उपयुक्त शक्ति प्रशिक्षण", "लचीलेपन और गतिशीलता अभ्यास", "संतुलन और समन्वय गतिविधियां", "हृदय संबंधी कंडीशनिंग", "पुनर्स्थापनात्मक गतिविधि और गहरा विश्राम", "प्रकृति-आधारित शारीरिक गतिविधि"]),
                "specific_concern": random.choice(["ऊपरी शरीर में तनाव पैटर्न", "कुछ भोजन के बाद पाचन संबंधी परेशानी", "दिन भर ऊर्जा में उतार-चढ़ाव", "नींद की गुणवत्ता और पुनर्स्थापना", "प्रयास के बाद रिकवरी का समय", "महत्वपूर्ण कार्यों के दौरान मानसिक फोकस", "दैनिक चुनौतियों के लिए तनाव प्रतिक्रियाएं"]),
                "body_message": random.choice(["विशिष्ट गतिविधियों के बाद सूक्ष्म ऊर्जा परिवर्तन", "विभिन्न खाद्य पदार्थों की पाचन प्रतिक्रियाएं", "तनाव या असुविधा के पैटर्न", "नींद और जागने की ऊर्जा की गुणवत्ता", "दिनचर्या के संबंध में मानसिक स्पष्टता", "शारीरिक संवेदनाओं से जुड़ी भावनात्मक अवस्थाएं", "कुछ प्रथाओं की ओर सहज आकर्षण"]),
                "health_insight": random.choice(["व्यक्तिगत लय और इष्टतम समय", "अनोखी पोषण जरूरतें", "गतिविधि के सबसे प्रभावी रूप", "गतिविधि और आराम का आदर्श संतुलन", "कल्याण को प्रभावित करने वाले पर्यावरणीय कारक", "स्वास्थ्य को प्रभावित करने वाले मन-शरीर संबंध", "दीर्घकालिक जीवन शक्ति के लिए निवारक प्रथाएं"])
            }
            
            # Gujarati variables
            gujarati_health_variables = {
                "health_energy": random.choice(["નવીનીકૃત જાગૃતિ", "વધારેલી સંવેદનશીલતા", "સંતુલિત પ્રભાવ", "પુનઃસ્થાપિત ફોકસ", "ઊર્જાવાન સ્પષ્ટતા", "મૃદુ ઉપચાર", "લયબદ્ધ સ્થિરીકરણ"]),
                "body_area": random.choice(["ચેતાતંત્ર અને તણાવ પ્રતિક્રિયાઓ", "પાચન કાર્ય અને પોષક તત્ત્વ શોષણ", "સ્નાયુ અને હાડકાંના સંરેખણ અને લવચિકતા", "હૃદયરોગ સ્વાસ્થ્ય અને લોહીનું પરિભ્રમણ", "શ્વસન ક્ષમતા અને ઓક્સિજન વિનિમય", "રોગપ્રતિકારક શક્તિ અને સ્થિતિસ્થાપકતા", "હોર્મોનલ સંતુલન અને નિયમન"]),
                "health_practice": random.choice(["સાતત્યપૂર્ણ ઊંઘની પેટર્ન સ્થાપિત કરવી", "રોજિંદી પ્રવૃત્તિઓમાં માઇન્ડફુલનેસને સમાવિષ્ટ કરવું", "દિવસ દરમિયાન યોગ્ય હાઇડ્રેશન સુનિશ્ચિત કરવું", "સ્થિરતાના સમયગાળા વચ્ચે હળવી ગતિશીલતા સમાવવી", "મનોયોગપૂર્વક ખાવા દ્વારા પાચન સ્વાસ્થ્યને ટેકો આપવો", "ડિજિટલ એક્સપોઝરની આસપાસ સીમાઓ બનાવવી", "નિયમિત રીતે પ્રકૃતિ સાથે જોડાણ કરવું"]),
                "physical_pattern": random.choice(["દિવસ દરમિયાન ઊર્જામાં ઉતાર-ચઢાવ", "ઊંઘ અને જાગૃતતાની ગુણવત્તા", "ભૂખ અને સંતોષના સંકેતો", "શારીરિક તણાવ અને આરામના ચક્રો", "હાઇડ્રેશનની સ્થિતિ અને અસરો", "વિવિધ ખોરાકની પ્રતિક્રિયાઓ", "પરિશ્રમ પછીના રિકવરી સમય"]),
                "energy_impact": random.choice(["માનસિક સ્પષ્ટતા અને કેન્દ્રિતતા", "ભાવનાત્મક સ્થિતિસ્થાપકતા", "શારીરિક સ્ટેમિના", "રોગપ્રતિકારક પ્રતિસાદ", "તણાવ વ્યવસ્થાપન ક્ષમતા", "સર્જનાત્મક પ્રવાહ", "અંતર્જ્ઞાનાત્મક જાગૃતિ"]),
                "wellness_goal": random.choice(["દિવસ દરમિયાન ટકાઉ ઊર્જા", "બહેતર રિકવરી અને સ્થિતિસ્થાપકતા", "સંતુલિત મિજાજ અને ભાવનાત્મક સુખાકારી", "વધારેલી માનસિક સ્પષ્ટતા અને કેન્દ્રિતતા", "મજબૂત રોગપ્રતિકારક શક્તિ અને ઘટાડેલો સોજો", "ઉત્તમ ગુણવત્તાની આરામ અને પુનઃસ્થાપન", "વધુ શારીરિક આરામ અને ગતિશીલતા"]),
                "diet_aspect": random.choice(["તમારા શરીરના લયના સંબંધમાં ભોજનનો સમય", "તમારી ચોક્કસ જરૂરિયાતો માટે મેક્રોન્યૂટ્રિયન્ટસનું સંતુલન", "દિવસ દરમિયાન હાઇડ્રેશન પ્રથાઓ", "ખોરાકની પસંદગીનું પોષક તત્વ ઘનત્વ", "ખાતી વખતે માઇન્ડફુલનેસ", "સંભવિત સંવેદનશીલતા અથવા અસહિષ્ણુતાઓ", "ખોરાક સ્ત્રોતોની વિવિધતા"]),
                "movement_approach": random.choice(["દિવસ દરમિયાન સાતત્યપૂર્ણ હળવી ગતિશીલતા", "તમારા શરીર માટે યોગ્ય શક્તિ તાલીમ", "લવચિકતા અને ગતિશીલતા પ્રથાઓ", "સંતુલન અને સંકલન પ્રવૃત્તિઓ", "હૃદયરોગ તંદુરસ્તી", "પુનઃસ્થાપક ગતિશીલતા અને ઊંડો આરામ", "પ્રકૃતિ-આધારિત શારીરિક પ્રવૃત્તિ"]),
                "specific_concern": random.choice(["ઉપલા શરીરમાં તણાવની પેટર્ન", "કેટલાક ભોજન પછી પાચન અગવડતા", "દિવસ દરમિયાન ઊર્જામાં ઉતાર-ચઢાવ", "ઊંઘની ગુણવત્તા અને પુનઃસ્થાપન", "પરિશ્રમ પછીનો રિકવરી સમય", "મહત્વપૂર્ણ કાર્યો દરમિયાન માનસિક કેન્દ્રિતતા", "રોજિંદા પડકારોને તણાવ પ્રતિક્રિયાઓ"]),
                "body_message": random.choice(["ચોક્કસ પ્રવૃત્તિઓ પછી સૂક્ષ્મ ઊર્જા બદલાવ", "વિવિધ ખોરાકની પાચન પ્રતિક્રિયાઓ", "તણાવ અથવા અસુવિધાની પેટર્ન", "ઊંઘ અને જાગૃત ઊર્જાની ગુણવત્તા", "રૂટિન સંબંધિત માનસિક સ્પષ્ટતા", "શારીરિક સંવેદનાઓ સાથે જોડાયેલી ભાવનાત્મક સ્થિતિઓ", "ચોક્કસ પ્રથાઓ તરફ અંતર્જ્ઞાનાત્મક ખેંચાણ"]),
                "health_insight": random.choice(["વ્યક્તિગત લય અને શ્રેષ્ઠ સમય", "અનોખી પોષણ જરૂરિયાતો", "ગતિશીલતાના સૌથી અસરકારક સ્વરૂપો", "પ્રવૃત્તિ અને આરામનું આદર્શ સંતુલન", "સુખાકારીને અસર કરતા પર્યાવરણીય પરિબળો", "સ્વાસ્થ્યને પ્રભાવિત કરતા મન-શરીર જોડાણો", "લાંબા ગાળાની શક્તિ માટે નિવારક પ્રથાઓ"]),
            }

            # Update variables based on language
            if language.lower() == "hindi":
                variables.update(hindi_health_variables)
                templates = hindi_templates
            elif language.lower() == "gujarati":
                variables.update(gujarati_health_variables)
                templates = gujarati_templates
            else:
                variables.update(health_variables)
                
        elif section == "General":
            # English templates
            templates = [
                "The cosmic energies shift meaningfully {timeframe} as {significant_planet} journeys through {planet_sign}{planet_retrograde}. This planetary influence brings {general_energy} to your overall experience, highlighting {life_theme} as a central focus. Pay attention to how {life_pattern} reveals important information about {life_understanding}. A situation involving {life_circumstance} benefits from {approach_strategy}, especially when considering {wisdom_perspective}. Your natural ability to {life_strength} serves you well, while awareness of {life_pattern} helps you navigate {life_challenge} with greater ease and understanding."
            ]
            
            # Hindi templates
            hindi_templates = [
                "ब्रह्मांडीय ऊर्जाएँ {timeframe} अर्थपूर्ण रूप से बदलती हैं क्योंकि {significant_planet} {planet_sign} से यात्रा करता है{planet_retrograde}। यह ग्रह प्रभाव आपके समग्र अनुभव में {general_energy} लाता है, {life_theme} को केंद्रीय फोकस के रूप में उजागर करता है। ध्यान दें कि कैसे {life_pattern} {life_understanding} के बारे में महत्वपूर्ण जानकारी प्रकट करता है। {life_circumstance} से जुड़ी स्थिति {approach_strategy} से लाभ पाती है, विशेष रूप से {wisdom_perspective} पर विचार करते समय। {life_strength} की आपकी प्राकृतिक क्षमता आपकी अच्छी तरह से सेवा करती है, जबकि {life_pattern} की जागरूकता आपको {life_challenge} को अधिक आसानी और समझ के साथ नेविगेट करने में मदद करती है।"
            ]
            
            # Gujarati templates
            gujarati_templates = [
                "બ્રહ્માંડીય ઊર્જાઓ {timeframe} અર્થપૂર્ણ રીતે બદલાય છે કારણ કે {significant_planet} {planet_sign}માંથી પસાર થાય છે{planet_retrograde}. આ ગ્રહનો પ્રભાવ તમારા સમગ્ર અનુભવમાં {general_energy} લાવે છે, {life_theme}ને કેન્દ્રીય ફોકસ તરીકે હાઇલાઇટ કરે છે. ધ્યાન આપો કે કેવી રીતે {life_pattern} {life_understanding} વિશે મહત્વપૂર્ણ માહિતી પ્રગટ કરે છે. {life_circumstance} સંબંધિત પરિસ્થિતિ {approach_strategy}થી લાભ મેળવે છે, ખાસ કરીને {wisdom_perspective} વિચારતી વખતે. {life_strength} કરવાની તમારી કુદરતી ક્ષમતા તમને સારી રીતે સેવા આપે છે, જ્યારે {life_pattern}ની જાગૃતિ તમને {life_challenge}ને વધુ સરળતા અને સમજણ સાથે નેવિગેટ કરવામાં મદદ કરે છે."
            ]
            
            # English variables
            general_variables = {
                "life_theme": random.choice(["authentic self-expression", "meaningful connections", "personal growth", "creative fulfillment", "balanced priorities", "purposeful action", "inner wisdom"]),
                "life_pattern": random.choice(["recurring themes", "timing synchronicities", "relationship dynamics", "growth opportunities", "challenge responses", "intuitive guidance", "energy cycles"]),
                "life_understanding": random.choice(["your authentic path", "relationship patterns", "personal rhythms", "growth processes", "inner wisdom", "life purpose", "natural abilities"]),
                "life_circumstance": random.choice(["unexpected change", "important decision", "relationship dynamic", "creative opportunity", "timing consideration", "resource allocation", "communication need"]),
                "approach_strategy": random.choice(["balanced consideration", "intuitive guidance", "practical wisdom", "patient observation", "authentic expression", "collaborative effort", "mindful action"]),
                "wisdom_perspective": random.choice(["long-term implications", "authentic values", "relationship impacts", "personal growth", "life balance", "purposeful direction", "inner truth"]),
                "life_strength": random.choice(["adapt to changing circumstances", "find creative solutions", "maintain balanced perspective", "connect authentically with others", "trust your intuitive guidance", "express yourself genuinely", "learn from experience"]),
                "life_challenge": random.choice(["unexpected changes", "timing pressures", "communication misunderstandings", "resource limitations", "competing priorities", "relationship complexities", "decision uncertainties"])
            }
            
            # Hindi variables
            hindi_general_variables = {
                "life_theme": random.choice(["प्रामाणिक आत्म-अभिव्यक्ति", "सार्थक कनेक्शन", "व्यक्तिगत विकास", "रचनात्मक संतुष्टि", "संतुलित प्राथमिकताएँ", "उद्देश्यपूर्ण क्रिया", "आंतरिक ज्ञान"]),
                "life_pattern": random.choice(["आवर्ती विषय", "समय सिंक्रोनिसिटी", "रिश्ते की गतिशीलता", "विकास के अवसर", "चुनौती प्रतिक्रियाएँ", "अंतर्ज्ञानी मार्गदर्शन", "ऊर्जा चक्र"]),
                "life_understanding": random.choice(["आपका प्रामाणिक पथ", "रिश्ते के पैटर्न", "व्यक्तिगत लय", "विकास प्रक्रियाएँ", "आंतरिक ज्ञान", "जीवन का उद्देश्य", "प्राकृतिक क्षमताएँ"]),
                "life_circumstance": random.choice(["अप्रत्याशित परिवर्तन", "महत्वपूर्ण निर्णय", "रिश्ते की गतिशीलता", "रचनात्मक अवसर", "समय विचार", "संसाधन आवंटन", "संचार आवश्यकता"]),
                "approach_strategy": random.choice(["संतुलित विचार", "अंतर्ज्ञानी मार्गदर्शन", "व्यावहारिक ज्ञान", "धैर्यपूर्ण अवलोकन", "प्रामाणिक अभिव्यक्ति", "सहयोगी प्रयास", "सचेत क्रिया"]),
                "wisdom_perspective": random.choice(["दीर्घकालिक प्रभाव", "प्रामाणिक मूल्य", "रिश्ते के प्रभाव", "व्यक्तिगत विकास", "जीवन संतुलन", "उद्देश्यपूर्ण दिशा", "आंतरिक सत्य"]),
                "life_strength": random.choice(["बदलती परिस्थितियों के अनुकूल बनना", "रचनात्मक समाधान खोजना", "संतुलित दृष्टिकोण बनाए रखना", "दूसरों के साथ प्रामाणिक रूप से जुड़ना", "अपने अंतर्ज्ञानी मार्गदर्शन पर भरोसा करना", "स्वयं को वास्तविक रूप से व्यक्त करना", "अनुभव से सीखना"]),
                "life_challenge": random.choice(["अप्रत्याशित परिवर्तन", "समय का दबाव", "संचार गलतफहमी", "संसाधन सीमाएँ", "प्रतिस्पर्धी प्राथमिकताएँ", "रिश्ते की जटिलताएँ", "निर्णय अनिश्चितताएँ"])
            }
            
            # Gujarati variables
            gujarati_general_variables = {
                "life_theme": random.choice(["પ્રામાણિક આત્મ-અભિવ્યક્તિ", "અર્થપૂર્ણ જોડાણો", "વ્યક્તિગત વિકાસ", "સર્જનાત્મક પરિપૂર્ણતા", "સંતુલિત પ્રાથમિકતાઓ", "હેતુપૂર્ણ ક્રિયા", "આંતરિક જ્ઞાન"]),
                "life_pattern": random.choice(["પુનરાવર્તિત થીમ", "સમય સિંક્રોનિસિટી", "સંબંધ ગતિશીલતા", "વિકાસની તકો", "પડકારની પ્રતિક્રિયાઓ", "અંતર્જ્ઞાન માર્ગદર્શન", "ઊર્જા ચક્રો"]),
                "life_understanding": random.choice(["તમારો પ્રામાણિક માર્ગ", "સંબંધોની પેટર્ન", "વ્યક્તિગત લય", "વિકાસ પ્રક્રિયાઓ", "આંતરિક જ્ઞાન", "જીવનનો હેતુ", "કુદરતી ક્ષમતાઓ"]),
                "life_circumstance": random.choice(["અણધારી બદલાવ", "મહત્વપૂર્ણ નિર્ણય", "સંબંધ ગતિશીલતા", "સર્જનાત્મક તક", "સમય વિચારણા", "સંસાધન ફાળવણી", "સંવાદ જરૂરિયાત"]),
                "approach_strategy": random.choice(["સંતુલિત વિચારણા", "અંતર્જ્ઞાન માર્ગદર્શન", "વ્યવહારિક જ્ઞાન", "ધીરજપૂર્વક નિરીક્ષણ", "પ્રામાણિક અભિવ્યક્તિ", "સહયોગી પ્રયાસ", "સચેત ક્રિયા"]),
                "wisdom_perspective": random.choice(["લાંબા ગાળાની અસરો", "પ્રામાણિક મૂલ્યો", "સંબંધ અસરો", "વ્યક્તિગત વિકાસ", "જીવન સંતુલન", "હેતુપૂર્ણ દિશા", "આંતરિક સત્ય"]),
                "life_strength": random.choice(["બદલાતી પરિસ્થિતિઓ સાથે અનુકૂળ થવું", "સર્જનાત્મક ઉકેલો શોધવા", "સંતુલિત દ્રષ્ટિકોણ જાળવવો", "અન્ય સાથે પ્રામાણિક રીતે જોડાવવું", "તમારા અંતર્જ્ઞાન માર્ગદર્શન પર વિશ્વાસ કરવો", "તમારી જાતને વાસ્તવિક રીતે વ્યક્ત કરવી", "અનુભવમાંથી શીખવું"]),
                "life_challenge": random.choice(["અણધારી બદલાવ", "સમયનું દબાણ", "સંવાદ ગેરસમજણો", "સંસાધન મર્યાદાઓ", "સ્પર્ધાત્મક પ્રાથમિકતાઓ", "સંબંધ જટિલતાઓ", "નિર્ણય અનિશ્ચિતતાઓ"])
            }

            # Update variables based on language
            if language.lower() == "hindi":
                variables.update(hindi_general_variables)
                templates = hindi_templates
            elif language.lower() == "gujarati":
                variables.update(gujarati_general_variables)
                templates = gujarati_templates
            else:
                variables.update(general_variables)
        
        # Select a template at random
        template = random.choice(templates)
        
        # Format the template with variables
        description = template.format(**variables)
        
        return description
    
    except Exception as e:
        logger.error(f"Error generating description for {section}: {e}")
        
        # Fallback descriptions for error cases
        fallback = {
            "Career": f"Your career path may have new developments {prediction_type.lower()}. Pay attention to opportunities that align with your strengths.",
            "Love": f"Relationships may bring unexpected energy {prediction_type.lower()}. Focus on communication and understanding.",
            "Finance": f"Financial matters require attention {prediction_type.lower()}. Consider your long-term goals when making decisions.",
            "Health": f"Pay attention to your body's signals {prediction_type.lower()}. Maintaining balance is key to your wellbeing.",
            "General": f"The cosmic energies {prediction_type.lower()} suggest focusing on what truly matters to you. Trust your intuition."
        }
        
        # Also translate the fallback if needed
        if language.lower() == "hindi":
            fallback_hindi = {
                "Career": f"{prediction_type.lower()} आपके करियर में नए विकास हो सकते हैं। अपनी ताकत के अनुरूप अवसरों पर ध्यान दें।",
                "Love": f"{prediction_type.lower()} संबंधों में अप्रत्याशित ऊर्जा आ सकती है। संवाद और समझ पर ध्यान दें।",
                "Finance": f"{prediction_type.lower()} वित्तीय मामलों पर ध्यान देने की आवश्यकता है। निर्णय लेते समय अपने दीर्घकालिक लक्ष्यों पर विचार करें।",
                "Health": f"{prediction_type.lower()} अपने शरीर के संकेतों पर ध्यान दें। आपके स्वास्थ्य के लिए संतुलन बनाए रखना महत्वपूर्ण है।",
                "General": f"{prediction_type.lower()} ब्रह्मांडीय ऊर्जाएँ संकेत देती हैं कि जो आपके लिए वास्तव में महत्वपूर्ण है उस पर ध्यान केंद्रित करें। अपनी अंतर्ज्ञान पर भरोसा करें।"
            }
            return fallback_hindi.get(section, fallback["General"])
        elif language.lower() == "gujarati":
            fallback_gujarati = {
                "Career": f"{prediction_type.lower()} તમારી કારકિર્દીમાં નવા વિકાસ થઈ શકે છે. તમારી શક્તિઓ સાથે સુસંગત તકો પર ધ્યાન આપો.",
                "Love": f"{prediction_type.lower()} સંબંધોમાં અણધારી ઊર્જા આવી શકે છે. સંદેશાવ્યવહાર અને સમજણ પર ધ્યાન કેન્દ્રિત કરો.",
                "Finance": f"{prediction_type.lower()} નાણાકીય બાબતો પર ધ્યાન આપવાની જરૂર છે. નિર્ણયો લેતી વખતે તમારા લાંબા ગાળાના લક્ષ્યો વિચારો.",
                "Health": f"{prediction_type.lower()} તમારા શરીરના સંકેતો પર ધ્યાન આપો. તમારી સુખાકારી માટે સંતુલન જાળવવું મહત્વપૂર્ણ છે.",
                "General": f"{prediction_type.lower()} બ્રહ્માંડીય ઊર્જાઓ સૂચવે છે કે તમારા માટે જે ખરેખર મહત્વપૂર્ણ છે તેના પર ધ્યાન કેન્દ્રિત કરો. તમારી અંતર્જ્ઞાન પર વિશ્વાસ રાખો."
            }
            return fallback_gujarati.get(section, fallback["General"])
        else:
            return fallback.get(section, fallback["General"])

def generate_horoscope(zodiac_sign: str, language: str, prediction_type: str, 
                       latitude: float, longitude: float) -> Dict[str, Any]:
    """Generate a complete horoscope prediction"""
    
    # Get current date and time
    today = date.today()
    
    # Determine the prediction date range based on the prediction type
    if prediction_type.lower() == "daily":
        start_date = today
        end_date = today
    elif prediction_type.lower() == "weekly":
        start_date = today
        end_date = today + timedelta(days=6)
    elif prediction_type.lower() == "monthly":
        start_date = today
        if today.month == 12:
            end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
    elif prediction_type.lower() == "yearly":
        start_date = today
        end_date = date(today.year + 1, today.month, today.day) - timedelta(days=1)
    else:
        return {"error": "Invalid prediction type. Please use Daily, Weekly, Monthly, or Yearly."}
    
    # Get planetary positions for the location
    planetary_positions = get_planetary_positions(datetime.now(), latitude, longitude)
    
    # Calculate aspects between planets
    aspects = generate_aspect_influences(planetary_positions)
    
    # In generate_horoscope function, modify the generate_description calls:
    general_prediction = generate_description("General", zodiac_sign, prediction_type, planetary_positions, aspects, language)
    career_prediction = generate_description("Career", zodiac_sign, prediction_type, planetary_positions, aspects, language)
    love_prediction = generate_description("Love", zodiac_sign, prediction_type, planetary_positions, aspects, language)
    finance_prediction = generate_description("Finance", zodiac_sign, prediction_type, planetary_positions, aspects, language)
    health_prediction = generate_description("Health", zodiac_sign, prediction_type, planetary_positions, aspects, language)
    
    # Generate lucky time and color
    lucky_time = generate_lucky_time(zodiac_sign, today)
    lucky_color = determine_lucky_color(zodiac_sign, today)
    
    # Create the horoscope structure
    horoscope = {
        "zodiac_sign": zodiac_sign,
        "prediction_type": prediction_type,
        "date_range": f"{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}",
        "lucky_color": lucky_color,
        "lucky_time": lucky_time,
        "predictions": {
            "general": general_prediction,
            "career": career_prediction,
            "love": love_prediction,
            "finance": finance_prediction,
            "health": health_prediction
        },
        "planetary_positions": planetary_positions,
        "planetary_aspects": aspects
    }
    
    # Translate only specific fields if needed
    if language.lower() in ["hindi", "gujarati"]:
        try:
            # Translate only the specified fields
            horoscope["zodiac_sign"] = translate_horoscope_field(horoscope["zodiac_sign"], language)
            horoscope["prediction_type"] = translate_horoscope_field(horoscope["prediction_type"], language)
            horoscope["date_range"] = translate_horoscope_field(horoscope["date_range"], language)
            horoscope["lucky_color"] = translate_horoscope_field(horoscope["lucky_color"], language)
            horoscope["lucky_time"] = translate_horoscope_field(horoscope["lucky_time"], language)
            
            logger.info(f"Translated specific horoscope fields to {language}")
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            horoscope["translation_error"] = f"Some translations may be incomplete: {str(e)}"
    
    return horoscope

def determine_lucky_color(zodiac_sign: str, date_obj: date) -> str:
    """Determine a lucky color based on zodiac sign and date"""
    colors = LUCKY_COLORS.get(zodiac_sign, ["Blue", "White", "Green"])
    random.seed(f"{zodiac_sign}_{date_obj}")
    return random.choice(colors)

def determine_lucky_number(zodiac_sign: str, date_obj: date) -> int:
    """Determine a lucky number based on zodiac sign and date"""
    numbers = LUCKY_NUMBERS.get(zodiac_sign, [1, 3, 5, 7, 9])
    random.seed(f"{zodiac_sign}_{date_obj}")
    if random.random() < 0.3:  # 30% chance to generate a different number
        return random.choice(numbers)
    else:
        return random.choice(numbers)

def translate_horoscope_field(text: str, target_language: str) -> str:
    """Translate specific horoscope fields using manual translation"""
    if target_language.lower() == "english":
        return text
    
    if target_language.lower() not in ["hindi", "gujarati"]:
        return text
    
    translations = HOROSCOPE_TRANSLATIONS.get(target_language.lower(), {})
    
    # Direct translation if available
    if text in translations:
        return translations[text]
    
    # Translate numbers in text
    translated_text = text
    for arabic, script in translations.items():
        if arabic.isdigit():
            translated_text = translated_text.replace(arabic, script)
    
    # Translate other words in the text
    words = translated_text.split()
    translated_words = []
    for word in words:
        # Remove punctuation for translation lookup
        clean_word = word.strip('.,!?;:')
        if clean_word in translations:
            translated_words.append(translations[clean_word] + word[len(clean_word):])
        else:
            translated_words.append(word)
    
    return ' '.join(translated_words)

HOROSCOPE_TRANSLATIONS = {
    "hindi": {
        # Numbers 0-9
        "0": "०", "1": "१", "2": "२", "3": "३", "4": "४", 
        "5": "५", "6": "६", "7": "७", "8": "८", "9": "९",
        
        # Time indicators
        "AM": "पूर्वाह्न (AM)", "PM": "अपराह्न (PM)", "to": "से",
        
        # Months
        "January": "जनवरी", "February": "फरवरी", "March": "मार्च", 
        "April": "अप्रैल", "May": "मई", "June": "जून", 
        "July": "जुलाई", "August": "अगस्त", "September": "सितंबर", 
        "October": "अक्टूबर", "November": "नवंबर", "December": "दिसंबर",
        
        # Zodiac signs
        "Aries": "मेष", "Taurus": "वृषभ", "Gemini": "मिथुन",
        "Cancer": "कर्क", "Leo": "सिंह", "Virgo": "कन्या",
        "Libra": "तुला", "Scorpio": "वृश्चिक", "Sagittarius": "धनु",
        "Capricorn": "मकर", "Aquarius": "कुंभ", "Pisces": "मीन",
        
        # Prediction types
        "Daily": "दैनिक", "Weekly": "साप्ताहिक", "Monthly": "मासिक", "Yearly": "वार्षिक",
        
        # Colors
        "Red": "लाल", "Orange": "नारंगी", "Yellow": "पीला", "Green": "हरा",
        "Blue": "नीला", "Purple": "बैंगनी", "Pink": "गुलाबी", "White": "सफेद",
        "Black": "काला", "Brown": "भूरा", "Gray": "स्लेटी", "Silver": "चांदी",
        "Gold": "सुनहरा", "Maroon": "मैरून", "Navy": "गहरा नीला", 
        "Turquoise": "फिरोजी", "Aqua": "आसमानी", "Sea Green": "समुद्री हरा",

                # Planet names
        "Sun": "सूर्य",
        "Moon": "चंद्र", 
        "Mercury": "बुध",
        "Venus": "शुक्र",
        "Mars": "मंगल",
        "Jupiter": "गुरु",
        "Saturn": "शनि",
        "Uranus": "अरुण",
        "Neptune": "वरुण", 
        "Pluto": "प्लूटो",
        "Rahu": "राहु",
        "Ketu": "केतु",
        
        # Aspect types
        "Conjunction": "युति",
        "Opposition": "विरोध",
        "Trine": "त्रिकोण",
        "Square": "चतुष्कोण",
        "Sextile": "षष्ठांश",
        "Quincunx": "अर्धषष्ठ",
        
        # Influence types
        "Harmonious": "अनुकूल",
        "Challenging": "चुनौतीपूर्ण",
        "Neutral": "तटस्थ",
        "Beneficial": "लाभकारी",
        "Difficult": "कठिन",
        "Positive": "सकारात्मक",
        "Negative": "नकारात्मक",
        "Mixed": "मिश्रित",
        
        # Common aspect description terms
        "degrees": "अंश",
        "with": "के साथ",
        "forms": "बनाता है",
        "creates": "निर्मित करता है",
        "brings": "लाता है",
        "indicates": "इंगित करता है",
        "suggests": "सुझाता है",
        "represents": "प्रतिनिधित्व करता है",
        "enhances": "बढ़ाता है",
        "supports": "समर्थन करता है",
        "challenges": "चुनौती देता है",
        "blocks": "अवरुद्ध करता है",
        "favors": "पक्ष में है",
        "energy": "ऊर्जा",
        "power": "शक्ति",
        "influence": "प्रभाव",
        "harmony": "सामंजस्य",
        "tension": "तनाव",
        "balance": "संतुलन",
        "conflict": "संघर्ष",
        "cooperation": "सहयोग",
        "communication": "संचार",
        "relationship": "संबंध",
        "creativity": "रचनात्मकता",
        "leadership": "नेतृत्व",
        "emotions": "भावनाएं",
        "intuition": "अंतर्ज्ञान",
        "transformation": "परिवर्तन",
        "expansion": "विस्तार",
        "restriction": "प्रतिबंध",
        "innovation": "नवाचार",
        "spirituality": "अध्यात्म",
        "material": "भौतिक",
        "financial": "वित्तीय",
        "career": "करियर",
        "health": "स्वास्थ्य",
        "love": "प्रेम",
        "marriage": "विवाह",
        "family": "परिवार",
        "luck": "भाग्य",
        "success": "सफलता",
        "growth": "विकास",
        "wisdom": "ज्ञान",
        "learning": "सीखना",
        "travel": "यात्रा",
        "home": "घर",
        "work": "काम",
        "business": "व्यापार",
        "partnership": "साझेदारी",
        "competition": "प्रतिस्पर्धा",
        "victory": "विजय",
        "defeat": "हार",
        "opportunity": "अवसर",
        "obstacle": "बाधा",
        "resolution": "समाधान",
        "achievement": "उपलब्धि"
    },
    
    "gujarati": {
        # Numbers 0-9
        "0": "૦", "1": "૧", "2": "૨", "3": "૩", "4": "૪", 
        "5": "૫", "6": "૬", "7": "૭", "8": "૮", "9": "૯",
        
        # Time indicators
        "AM": "પૂર્વાહ્ન (AM)", "PM": "અપરાહ્ન (PM)", "to": "થી",
        
        # Months
        "January": "જાન્યુઆરી", "February": "ફેબ્રુઆરી", "March": "માર્ચ",
        "April": "એપ્રિલ", "May": "મે", "June": "જૂન",
        "July": "જુલાઈ", "August": "ઑગસ્ટ", "September": "સપ્ટેમ્બર",
        "October": "ઑક્ટોબર", "November": "નવેમ્બર", "December": "ડિસેમ્બર",
        
        # Zodiac signs
        "Aries": "મેષ", "Taurus": "વૃષભ", "Gemini": "મિથુન",
        "Cancer": "કર્ક", "Leo": "સિંહ", "Virgo": "કન્યા",
        "Libra": "તુલા", "Scorpio": "વૃશ્ચિક", "Sagittarius": "ધનુ",
        "Capricorn": "મકર", "Aquarius": "કુંભ", "Pisces": "મીન",
        
        # Prediction types
        "Daily": "દૈનિક", "Weekly": "સાપ્તાહિક", "Monthly": "માસિક", "Yearly": "વાર્ષિક",
        
        # Colors
        "Red": "લાલ", "Orange": "નારંગી", "Yellow": "પીળો", "Green": "લીલો",
        "Blue": "વાદળી", "Purple": "જાંબુડી", "Pink": "ગુલાબી", "White": "સફેદ",
        "Black": "કાળો", "Brown": "ભૂરો", "Gray": "રાખોડી", "Silver": "ચાંદી",
        "Gold": "સોનેરી", "Maroon": "મરૂન", "Navy": "ઘેરો વાદળી",
        "Turquoise": "ફિરોજી", "Aqua": "આકાશી", "Sea Green": "દરિયાઈ લીલો",

        # Planet names
        "Sun": "સૂર્ય",
        "Moon": "ચંદ્ર",
        "Mercury": "બુધ", 
        "Venus": "શુક્ર",
        "Mars": "મંગળ",
        "Jupiter": "ગુરુ",
        "Saturn": "શનિ",
        "Uranus": "અરુણ",
        "Neptune": "વરુણ",
        "Pluto": "પ્લુટો",
        "Rahu": "રાહુ",
        "Ketu": "કેતુ",
        
        # Aspect types
        "Conjunction": "યુતિ",
        "Opposition": "વિરોધ", 
        "Trine": "ત્રિકોણ",
        "Square": "ચતુષ્કોણ",
        "Sextile": "ષષ્ઠાંશ",
        "Quincunx": "અર્ધષષ્ઠ",
        
        # Influence types
        "Harmonious": "અનુકૂળ",
        "Challenging": "પડકારજનક",
        "Neutral": "તટસ્થ",
        "Beneficial": "લાભકારી", 
        "Difficult": "કઠિન",
        "Positive": "સકારાત્મક",
        "Negative": "નકારાત્મક",
        "Mixed": "મિશ્રિત",
        
        # Common aspect description terms
        "degrees": "અંશ",
        "with": "સાથે",
        "forms": "બનાવે છે",
        "creates": "સર્જન કરે છે",
        "brings": "લાવે છે",
        "indicates": "સૂચવે છે",
        "suggests": "સૂચવે છે",
        "represents": "પ્રતિનિધિત્વ કરે છે",
        "enhances": "વધારે છે",
        "supports": "સમર્થન કરે છે",
        "challenges": "પડકાર આપે છે",
        "blocks": "અવરોધે છે",
        "favors": "પક્ષમાં છે",
        "energy": "ઊર્જા",
        "power": "શક્તિ",
        "influence": "પ્રભાવ",
        "harmony": "સુમેળ",
        "tension": "તણાવ",
        "balance": "સંતુલન",
        "conflict": "સંઘર્ષ",
        "cooperation": "સહકાર",
        "communication": "સંવાદ",
        "relationship": "સંબંધ",
        "creativity": "સર્જનાત્મકતા",
        "leadership": "નેતૃત્વ",
        "emotions": "લાગણીઓ",
        "intuition": "અંતર્જ્ઞાન",
        "transformation": "રૂપાંતરણ",
        "expansion": "વિસ્તરણ",
        "restriction": "પ્રતિબંધ",
        "innovation": "નવોત્પાદન",
        "spirituality": "આધ્યાત્મ",
        "material": "ભૌતિક",
        "financial": "નાણાકીય",
        "career": "કારકિર્દી",
        "health": "આરોગ્ય",
        "love": "પ્રેમ",
        "marriage": "લગ્ન",
        "family": "કુટુંબ",
        "luck": "નસીબ",
        "success": "સફળતા",
        "growth": "વૃદ્ધિ",
        "wisdom": "જ્ઞાન",
        "learning": "શીખવું",
        "travel": "પ્રવાસ",
        "home": "ઘર",
        "work": "કામ",
        "business": "વ્યવસાય",
        "partnership": "ભાગીદારી",
        "competition": "સ્પર્ધા",
        "victory": "વિજય",
        "defeat": "હાર",
        "opportunity": "તક",
        "obstacle": "અવરોધ",
        "resolution": "ઉકેલ",
        "achievement": "સિદ્ધિ"
    }
}

# Manual translation dictionaries for Panchang data
PANCHANG_TRANSLATIONS = {
     
    "hindi": {
        # Numbers 0-9
        "0": "०", "1": "१", "2": "२", "3": "३", "4": "४", 
        "5": "५", "6": "६", "7": "७", "8": "८", "9": "९",
        
        # Time indicators
        "AM": "पूर्वाह्न", "PM": "अपराह्न",
        
        # Days of week (sample)
        "Monday": "सोमवार", "Tuesday": "मंगलवार", "Wednesday": "बुधवार", "Thursday": "गुरुवार", "Friday": "शुक्रवार", "Saturday": "शनिवार", "Sunday": "रविवार",
        
        # Months (sample)
        "January": "जनवरी", "February": "फरवरी", "March": "मार्च", "April": "अप्रैल", "May": "मई", "June": "जून", "July": "जुलाई", "August": "अगस्त", "September": "सितंबर", "October": "अक्टूबर", "November": "नवंबर", "December": "दिसंबर",
        
        # Planets (sample)
        "Sun": "सूर्य", "Moon": "चंद्र", "Mercury": "बुध", "Venus": "शुक्र", "Mars": "मंगल", "Jupiter": "गुरु", "Saturn": "शनि", "Rahu": "राहु", "Ketu": "केतु", "Uranus": "अरुण", "Neptune": "वरुण", "Pluto": "प्लूटो",
        
        # Nakshatras 
        "Ashwini": "अश्विनी", 
        "Bharani": "भरणी", 
        "Krittika": "कृत्तिका", 
        "Rohini": "रोहिणी", 
        "Mrigashira": "मृगशिरा", 
        "Ardra": "आर्द्रा", 
        "Punarvasu": "पुनर्वसु", 
        "Pushya": "पुष्य", 
        "Ashlesha": "आश्रेषा", 
        "Magha": "मघा", 
        "Purva Phalguni": "पूर्व फाल्गुनी", 
        "Uttara Phalguni": "उत्तर फाल्गुनी", 
        "Hasta": "हस्त", 
        "Chitra": "चित्रा", 
        "Swati": "स्वाति", 
        "Vishakha": "विशाखा", 
        "Anuradha": "अनुराधा", 
        "Jyeshtha": "ज्येष्ठा", 
        "Mula": "मूला", 
        "Purva Ashadha": "पूर्वाषाढा", 
        "Uttara Ashadha": "उत्तराषाढा", 
        "Shravana": "श्रवण", "Dhanishta": 
        "धनिष्ठा", "Shatabhisha": "शतभिषक", 
        "Purva Bhadrapada": "पूर्व भाद्रपदा", 
        "Uttara Bhadrapada": "उत्तर भाद्रपदा", 
        "Revati": "रेवती",
        
        # Nakshatra properties 
        "Ashwini Kumaras": "अश्विनी कुमार",
        "Yama (God of Death)": "यम (मृत्यु के देवता)",
        "Agni (Fire God)": "अग्नि (आग के देवता)",
        "Brahma (Creator)": "ब्रह्मा (सृष्टिकर्ता)",
        "Soma (Moon God)": "सोम (चाँद के देवता)",
        "Rudra (Storm God)": "रुद्र (तूफान के देवता)",
        "Aditi (Goddess of Boundlessness)": "आदिति (असीमता की देवी)",
        "Brihaspati (Jupiter)": "बृहस्पति (गुरु)",
        "Naga (Serpent Gods)": "नाग (नाग देवता)",
        "Pitris (Ancestors)": "पितृ (पूर्वज)",
        "Bhaga (God of Enjoyment)": "भाग (आनंद के देवता)",
        "Aryaman (God of Contracts)": "आर्यमन (अनुबंधों के देवता)",
        "Savitar (Aspect of Sun)": "सविता (सूर्य का पहलू)",
        "Vishvakarma (Divine Architect)": "विश्वकर्मा (दिव्य वास्तुकार)",
        "Vayu (Wind God)": "वायु (वायु देवता)",
        "Indra-Agni (Gods of Power and Fire)": "इंद्र-आग्नि (शक्ति और आग के देवता)",
        "Mitra (God of Friendship)": "मित्र (मित्रता के देवता)",
        "Indra (King of Gods)": "इंद्र (देवताओं के राजा)",
        "Nirriti (Goddess of Destruction)": "निरृति (विनाश की देवी)",
        "Apas (Water Goddesses)": "आपस (जल देवियाँ)",
        "Vishvedevas (Universal Gods)": "विश्वेदेव (सार्वभौमिक देवता)",
        "Vishnu": "विष्णु",
        "Vasus (Gods of Abundance)": "वासु (समृद्धि के देवता)",
        "Varuna (God of Cosmic Waters)": "वरुण (कॉस्मिक जल के देवता)",
        "Aja Ekapada (One-footed Goat)": "अजा एकपाद (एक-पैर वाला बकरा)",
        "Ahirbudhnya (Serpent of the Depths)": "अहिरभुदन्य (गहराइयों का नाग)",
        "Pushan (Nourishing God)": "पुषण (पोषण करने वाला देवता)",

        #NAKSHTRA QUALITIES in hindi
        "Energy, activity, enthusiasm, courage, healing abilities, and competitive spirit.": "ऊर्जा, गतिविधि, उत्साह, साहस, उपचार क्षमताएँ, और प्रतिस्पर्धात्मक आत्मा।",
        "Discipline, restraint, assertiveness, transformation, and creative potential.": "अनुशासन, संयम, आत्मविश्वास, परिवर्तन, और रचनात्मक क्षमता।",
        "Purification, clarity, transformation, ambition, and leadership.": "शुद्धिकरण, स्पष्टता, परिवर्तन, महत्वाकांक्षा, और नेतृत्व।",
        "Growth, fertility, prosperity, sensuality, and creativity.": "विकास, प्रजनन, समृद्धि, संवेदीता, और रचनात्मकता।",
        "Gentleness, curiosity, searching nature, adaptability, and communication skills.": "कोमलता, जिज्ञासा, खोजी स्वभाव, अनुकूलनशीलता, और संचार कौशल।",
        "Transformation through challenge, intensity, passion, and regenerative power.": "चुनौती, तीव्रता, जुनून, और पुनर्जनन शक्ति के माध्यम से परिवर्तन।",
        "Renewal, optimism, wisdom, generosity, and expansiveness.": "नवीकरण, आशावाद, ज्ञान, उदारता, और विस्तार।",
        "Nourishment, prosperity, spiritual growth, nurturing, and stability.": "पोषण, समृद्धि, आध्यात्मिक विकास, पालन-पोषण, और स्थिरता।",
        "Intuition, mystical knowledge, healing abilities, intensity, and transformative power.": "अंतर्ज्ञान, रहस्यमय ज्ञान, उपचार क्षमताएँ, तीव्रता, और परिवर्तनकारी शक्ति।",
        "Leadership, power, ancestry, dignity, and social responsibility.": "नेतृत्व, शक्ति, पूर्वज, गरिमा, और सामाजिक जिम्मेदारी।",
        "Creativity, enjoyment, romance, social grace, and playfulness.": "रचनात्मकता, आनंद, रोमांस, सामाजिकGrace, और खेल भावना।",
        "Balance, harmony, partnership, social contracts, and graceful power.": "संतुलन, सामंजस्य, साझेदारी, सामाजिक अनुबंध, औरGraceful शक्ति।",
        "Skill, dexterity, healing abilities, practical intelligence, and manifestation.": "कौशल, चतुराई, उपचार क्षमताएँ, व्यावहारिक बुद्धिमत्ता, और प्रकट करना।",
        "Creativity, design skills, beauty, brilliance, and multi-faceted talents.": "रचनात्मकता, डिज़ाइन कौशल, सुंदरता, चमक, और बहुआयामी प्रतिभाएँ।",
        "Independence, adaptability, movement, self-sufficiency, and scattered brilliance.": "स्वतंत्रता, अनुकूलनशीलता, आंदोलन, आत्मनिर्भरता, और बिखरी हुई चमक।",
        "Determination, focus, goal achievement, leadership, and purposeful effort.": "निश्चितता, ध्यान, लक्ष्य प्राप्ति, नेतृत्व, और उद्देश्यपूर्ण प्रयास।",
        "Friendship, cooperation, devotion, loyalty, and success through relationships.": "मित्रता, सहयोग, भक्ति, निष्ठा, और संबंधों के माध्यम से सफलता।",
        "Courage, leadership, protective qualities, seniority, and power.": "साहस, नेतृत्व, सुरक्षा गुण, वरिष्ठता, और शक्ति।",
        "Destruction for creation, getting to the root, intensity, and transformative power.": "निर्माण के लिए विनाश, जड़ तक पहुँचना, तीव्रता, और परिवर्तनकारी शक्ति।",
        "Early victory, invigoration, purification, and unquenchable energy.": "प्रारंभिक विजय, उत्साह, शुद्धिकरण, और अग्निशामक ऊर्जा।",
        "Universal principles, later victory, balance of power, and enduring success.": "सार्वभौमिक सिद्धांत, बाद की विजय, शक्ति का संतुलन, और स्थायी सफलता।",
        "Learning, wisdom through listening, connectivity, devotion, and fame.": "सीखना, सुनने के माध्यम से ज्ञान, कनेक्टिविटी, भक्ति, और प्रसिद्धि।",
        "Wealth, abundance, music, rhythm, and generous spirit.": "धन, प्रचुरता, संगीत, लय, और उदार आत्मा।",
        "Healing, scientific mind, independence, mystical abilities, and expansive awareness.": "उपचार, वैज्ञानिक मन, स्वतंत्रता, रहस्यमय क्षमताएँ, और विस्तृत जागरूकता।",
        "Intensity, fiery wisdom, transformative vision, and spiritual awakening.": "तीव्रता, अग्निमय ज्ञान, परिवर्तनकारी दृष्टि, और आध्यात्मिक जागरण।",
        "Deep truth, profound wisdom, serpentine power, and regenerative abilities.": "गहरी सच्चाई, गहरा ज्ञान, नागिन शक्ति, और पुनर्जनन क्षमताएँ।",
        "Nourishment, protection during transitions, abundance, and nurturing wisdom.": "पोषण, संक्रमण के दौरान सुरक्षा, प्रचुरता, और पालन-पोषण ज्ञान।",

        # Choghadiya
        "Amrit": "अमृत",
        "Shubh": "शुभ",
        "Labh": "लाभ",
        "Char": "चर",
        "Kaal": "काल",
        "Rog": "रोग",
        "Udveg": "उद्वेग",

        # Nature
        "Good": "शुभ",
        "Bad": "अशुभ",
        "Neutral": "सामान्य",
        "Excellent": "उत्तम",

 # Choghadiya meanings
        "Nectar - Most auspicious for all activities": "अमृत - सभी गतिविधियों के लिए सर्वाधिक शुभ",
        "Auspicious - Good for all positive activities": "शुभ - सभी सकारात्मक गतिविधियों के लिए अच्छा",
        "Profit - Excellent for business and financial matters": "लाभ - व्यापार और वित्तीय मामलों के लिए उत्कृष्ट",
        "Movement - Good for travel and dynamic activities": "चर - यात्रा और गतिशील गतिविधियों के लिए अच्छा",
        "Death - Inauspicious, avoid important activities": "काल - अशुभ, महत्वपूर्ण गतिविधियों से बचें",
        "Disease - Avoid health-related decisions": "रोग - स्वास्थ्य संबंधी निर्णयों से बचें",
        "Anxiety - Mixed results, proceed with caution": "उद्वेग - मिश्रित परिणाम, सावधानी से आगे बढ़ें",

    # Hora meanings
        "Authority, leadership, government work": "अधिकार, नेतृत्व, सरकारी कार्य",
        "Emotions, family matters, water-related activities": "भावनाएं, पारिवारिक मामले, जल संबंधी गतिविधियां",
        "Energy, sports, real estate, surgery": "ऊर्जा, खेल, अचल संपत्ति, शल्य चिकित्सा",
        "Communication, education, business, travel": "संचार, शिक्षा, व्यापार, यात्रा",
        "Wisdom, spirituality, teaching, ceremonies": "ज्ञान, आध्यात्म, शिक्षण, समारोह",
        "Arts, beauty, relationships, luxury": "कला, सुंदरता, रिश्ते, विलासिता",
        "Delays, obstacles, hard work, patience required": "देरी, बाधाएं, कड़ी मेहनत, धैर्य की आवश्यकता",

    # Inauspicious periods
        "Rahu Kaal is considered an inauspicious time for starting important activities.": "राहु काल को महत्वपूर्ण गतिविधियां शुरू करने के लिए अशुभ समय माना जाता है।",
        "Gulika Kaal is considered an unfavorable time period.": "गुलिका काल को एक प्रतिकूल समय अवधि माना जाता है।",
        "Yamaghanta is considered inauspicious for important activities.": "यमघंटा को महत्वपूर्ण गतिविधियों के लिए अशुभ माना जाता है।",
        
        # Subh Muhurats
        "Brahma Muhurat": "ब्रह्म मुहूर्त",
        "Sacred early morning hours ideal for spiritual practices.": "आध्यात्मिक अभ्यासों के लिए आदर्श पवित्र प्रातःकालीन घंटे।",
        "Abhijit Muhurat": "अभिजीत मुहूर्त",
        "Highly auspicious for starting new ventures.": "नए उपक्रमों की शुरुआत के लिए अत्यधिक शुभ।",
        
        # Tithi Names
        "Shukla Pratipada": "शुक्ल प्रतिपदा",
        "Shukla Dwitiya": "शुक्ल द्वितीया",
        "Shukla Tritiya": "शुक्ल तृतीया",
        "Shukla Chaturthi": "शुक्ल चतुर्थी",
        "Shukla Panchami": "शुक्ल पंचमी",
        "Shukla Shashthi": "शुक्ल षष्ठी",
        "Shukla Saptami": "शुक्ल सप्तमी",
        "Shukla Ashtami": "शुक्ल अष्टमी",
        "Shukla Navami": "शुक्ल नवमी",
        "Shukla Dashami": "शुक्ल दशमी",
        "Shukla Ekadashi": "शुक्ल एकादशी",
        "Shukla Dwadashi": "शुक्ल द्वादशी",
        "Shukla Trayodashi": "शुक्ल त्रयोदशी",
        "Shukla Chaturdashi": "शुक्ल चतुर्दशी",
        "Purnima": "पूर्णिमा",
        "Krishna Pratipada": "कृष्ण प्रतिपदा",
        "Krishna Dwitiya": "कृष्ण द्वितीया",
        "Krishna Tritiya": "कृष्ण तृतीया",
        "Krishna Chaturthi": "कृष्ण चतुर्थी",
        "Krishna Panchami": "कृष्ण पंचमी",
        "Krishna Shashthi": "कृष्ण षष्ठी",
        "Krishna Saptami": "कृष्ण सप्तमी",
        "Krishna Ashtami": "कृष्ण अष्टमी",
        "Krishna Navami": "कृष्ण नवमी",
        "Krishna Dashami": "कृष्ण दशमी",
        "Krishna Ekadashi": "कृष्ण एकादशी",
        "Krishna Dwadashi": "कृष्ण द्वादशी",
        "Krishna Trayodashi": "कृष्ण त्रयोदशी",
        "Krishna Chaturdashi": "कृष्ण चतुर्दशी",
        "Amavasya": "अमावस्या",

        #Tithi deity
        "Parvati": "पार्वती",
        "Ganesha": "गणेश",
        "Skanda": "स्कंद",
        "Durga": "दुर्गा",
        "Lakshmi": "लक्ष्मी",
        "Saraswati": "सरस्वती",
        "Shiva": "शिव",
        "Vishnu": "विष्णु",
        "Gauri": "गौरी",
        "Naga Devata": "नाग देवता",
        "Kali, Rudra": "काली, रुद्र",

        #TITHI SPECIALS
        "Auspicious for rituals, marriage, travel":" शुभ कार्यों, विवाह, यात्रा के लिए शुभ",
        "Good for housework, learning":" घर के काम, अध्ययन के लिए अच्छा",
        "Celebrated as Gauri Tritiya (Teej)":"गौरी तृतीया (तीज) के रूप में मनाया जाता है",
        "Sankashti/Ganesh Chaturthi":"संकष्टी/गणेश चतुर्थी",
        "Nag Panchami, Saraswati Puja":"नाग पंचमी, सरस्वती पूजा",
        "Skanda Shashthi, children's health":"स्कंद षष्ठी, बच्चों के स्वास्थ्य के लिए",
        "Ratha Saptami, start of auspicious work":"रथ सप्तमी, शुभ कार्यों की शुरुआत",
        "Kala Ashtami, Durga Puja":"कला अष्टमी, दुर्गा पूजा",
        "Mahanavami, victory over evil": "महानवमी, बुराई पर विजय",
        "Vijayadashami/Dussehra": "विजयादशमी/दशहरा",
        "Fasting day, spiritually uplifting": "उपवास का दिन, आध्यात्मिक उन्नति के लिए",
        "Breaking Ekadashi fast (Parana)": "एकादशी उपवास तोड़ना (पराण)",
        "Pradosh Vrat, Dhanteras": "प्रदोष व्रत, धनतेरस",
        "Narak Chaturdashi, spiritual cleansing": "नरक चतुर्दशी, आध्यात्मिक शुद्धि के लिए",
        "Full moon/new moon, ideal for puja, shraddha": "पूर्णिमा/अमावस्या, पूजा, श्राद्ध के लिए आदर्श",
        "Waxing phase of the moon (new to full moon)": "चाँद की वर्धमान अवस्था (नया से पूर्णिमा तक)",
        "Waning phase (full to new moon)": "चाँद की क्षीण अवस्था (पूर्णिमा से अमावस्या तक)",

        
        # Yoga in hindi
        "Vishkambha": "विश्कम्भ",
        "Priti": "प्रीति",
        "Ayushman": "आयुष्मान",
        "Saubhagya": "सौभाग्य",
        "Shobhana": "शोभना",
        "Atiganda": "अतिगंड",
        "Sukarman": "सुकर्मन",
        "Dhriti": "धृति",
        "Shula": "शूल",
        "Ganda": "गंड",
        "Vriddhi": "वृद्धि",
        "Dhruva": "ध्रुवा",
        "Vyaghata": "व्याघात",
        "Harshana": "हर्षण",
        "Vajra": "वज्र",
        "Siddhi": "सिद्धि",
        "Vyatipata": "व्यतिपात",
        "Variyana": "वरियान",
        "Parigha": "परिघ",
        "Shiva": "शिव",
        "Siddha": "सिद्ध",
        "Sadhya": "साध्य",
        "Shubha": "शुभ",
        "Shukla": "शुक्ल",
        "Brahma": "ब्रह्म",
        "Indra": "इंद्र",
        "Vaidhriti": "वैधृति",

        # Common terms
        "Sunrise": "सूर्योदय", "Sunset": "सूर्यास्त",
        "Rahu Kaal": "राहु काल", "Gulika Kaal": "गुलिका काल",
        "description": "विवरण", "nature": "प्रकृति",

               # Tithi Descriptions
        "Good for starting new ventures and projects. Favorable for planning and organization. Avoid excessive physical exertion and arguments.": "नए उद्यमों और परियोजनाओं की शुरुआत के लिए अच्छा। योजना और संगठन के लिए अनुकूल। अत्यधिक शारीरिक परिश्रम और तर्कों से बचें।",
        "Excellent for intellectual pursuits and learning. Suitable for purchases and agreements. Avoid unnecessary travel and overindulgence.": "बौद्धिक गतिविधियों और शिक्षा के लिए उत्कृष्ट। खरीदारी और समझौतों के लिए उपयुक्त। अनावश्यक यात्रा और अति से बचें।",
        "Auspicious for all undertakings, especially weddings and partnerships. Benefits from charitable activities. Avoid conflicts and hasty decisions.": "सभी कार्यों के लिए शुभ, विशेषकर विवाह और साझेदारी। दान के कार्यों से लाभ। संघर्ष और जल्दबाजी के निर्णयों से बचें।",
        "Good for worship of Lord Ganesha and removing obstacles. Favorable for creative endeavors. Avoid starting major projects or signing contracts.": "भगवान गणेश की पूजा और बाधाओं को दूर करने के लिए अच्छा। रचनात्मक प्रयासों के लिए अनुकूल। बड़ी परियोजनाएं शुरू करने या अनुबंध पर हस्ताक्षर करने से बचें।",
        "Excellent for education, arts, and knowledge acquisition. Good for competitions and tests. Avoid unnecessary arguments and rash decisions.": "शिक्षा, कला और ज्ञान प्राप्ति के लिए उत्कृष्ट। प्रतियोगिताओं और परीक्षाओं के लिए अच्छा। अनावश्यक बहस और जल्दबाजी के निर्णयों से बचें।",
        "Favorable for victory over enemies and completion of difficult tasks. Good for health initiatives. Avoid procrastination and indecisiveness.": "शत्रुओं पर विजय और कठिन कार्यों को पूरा करने के लिए अनुकूल। स्वास्थ्य पहलों के लिए अच्छा। टालमटोल और अनिर्णय से बचें।",
        "Excellent for health, vitality, and leadership activities. Good for starting treatments. Avoid excessive sun exposure and ego conflicts.": "स्वास्थ्य, जीवन शक्ति और नेतृत्व गतिविधियों के लिए उत्कृष्ट। उपचार शुरू करने के लिए अच्छा। अत्यधिक धूप और अहंकार संघर्षों से बचें।",
        "Good for meditation, spiritual practices, and self-transformation. Favorable for fasting. Avoid impulsive decisions and major changes.": "ध्यान, आध्यात्मिक प्रथाओं और आत्म-परिवर्तन के लिए अच्छा। उपवास के लिए अनुकूल। आवेगशील निर्णयों और बड़े बदलावों से बचें।",
        "Powerful for spiritual practices and overcoming challenges. Good for courage and strength. Avoid unnecessary risks and confrontations.": "आध्यात्मिक प्रथाओं और चुनौतियों पर काबू पाने के लिए शक्तिशाली। साहस और शक्ति के लिए अच्छा। अनावश्यक जोखिमों और टकरावों से बचें।",
        "Favorable for righteous actions and religious ceremonies. Good for ethical decisions. Avoid dishonesty and unethical compromises.": "धर्म के कार्यों और धार्मिक समारोहों के लिए अनुकूल। नैतिक निर्णयों के लिए अच्छा। बेईमानी और अनैतिक समझौतों से बचें।",
        "Highly auspicious for spiritual practices, fasting, and worship of Vishnu. Benefits from restraint and self-control. Avoid overeating and sensual indulgences.": "आध्यात्मिक प्रथाओं, उपवास और विष्णु की पूजा के लिए अत्यधिक शुभ। संयम और आत्म-नियंत्रण से लाभ। अधिक खाने और इंद्रिय सुखों से बचें।",
        "Good for breaking fasts and charitable activities. Favorable for generosity and giving. Avoid selfishness and stubbornness today.": "उपवास तोड़ने और दान के कार्यों के लिए अच्छा। उदारता और देने के लिए अनुकूल। आज स्वार्थ और हठ से बचें।",
        "Excellent for beauty treatments, romance, and artistic pursuits. Good for sensual pleasures. Avoid excessive attachment and jealousy.": "सौंदर्य उपचार, रोमांस और कलात्मक गतिविधियों के लिए उत्कृष्ट। इंद्रिय सुखों के लिए अच्छा। अत्यधिक लगाव और ईर्ष्या से बचें।",
        "Powerful for worship of Lord Shiva and spiritual growth. Good for finishing tasks. Avoid beginning major projects and hasty conclusions.": "भगवान शिव की पूजा और आध्यात्मिक विकास के लिए शक्तिशाली। कार्यों को समाप्त करने के लिए अच्छा। बड़ी परियोजनाएं शुरू करने और जल्दबाजी के निष्कर्षों से बचें।",
        "Highly auspicious for spiritual practices, especially related to the moon. Full emotional and mental strength. Avoid emotional instability and overthinking.": "आध्यात्मिक प्रथाओं के लिए अत्यधिक शुभ, विशेषकर चंद्रमा से संबंधित। पूर्ण भावनात्मक और मानसिक शक्ति। भावनात्मक अस्थिरता और अधिक सोचने से बचें।",
        "Suitable for planning and reflection. Good for introspection and simple rituals. Avoid major launches or important beginnings.": "योजना और चिंतन के लिए उपयुक्त। आत्मनिरीक्षण और सरल अनुष्ठानों के लिए अच्छा। बड़े लॉन्च या महत्वपूर्ण शुरुआतों से बचें।",
        "Favorable for intellectual pursuits and analytical work. Good for research and study. Avoid impulsive decisions and confrontations.": "बौद्धिक गतिविधियों और विश्लेषणात्मक कार्यों के लिए अनुकूल। अनुसंधान और अध्ययन के लिए अच्छा। आवेगशील निर्णयों और टकरावों से बचें।",
        "Good for activities requiring courage and determination. Favorable for assertive actions. Avoid aggression and unnecessary force.": "साहस और दृढ़ता की आवश्यकता वाली गतिविधियों के लिए अच्छा। मुखर कार्यों के लिए अनुकूल। आक्रामकता और अनावश्यक बल से बचें।",
        "Suitable for removing obstacles and solving problems. Good for analytical thinking. Avoid starting new ventures and major purchases.": "बाधाओं को दूर करने और समस्याओं को हल करने के लिए उपयुक्त। विश्लेषणात्मक सोच के लिए अच्छा। नए उद्यम शुरू करने और बड़ी खरीदारी से बचें।",
        "Favorable for education, learning new skills, and artistic pursuits. Good for communication. Avoid arguments and misunderstandings.": "शिक्षा, नई कुशलताएं सीखने और कलात्मक गतिविधियों के लिए अनुकूल। संचार के लिए अच्छा। बहस और गलतफहमियों से बचें।",
        "Good for competitive activities and overcoming challenges. Favorable for strategic planning. Avoid conflict and excessive competition.": "प्रतिस्पर्धी गतिविधियों और चुनौतियों पर काबू पाने के लिए अच्छा। रणनीतिक योजना के लिए अनुकूल। संघर्ष और अत्यधिक प्रतिस्पर्धा से बचें।",
        "Suitable for health treatments and healing. Good for physical activities and exercise. Avoid overexertion and risky ventures.": "स्वास्थ्य उपचार और चिकित्सा के लिए उपयुक्त। शारीरिक गतिविधियों और व्यायाम के लिए अच्छा। अत्यधिक परिश्रम और जोखिम भरे उपक्रमों से बचें।",
        "Powerful for devotional activities, especially to Lord Krishna. Good for fasting and spiritual practices. Avoid excessive materialism and sensual indulgence.": "भक्ति गतिविधियों के लिए शक्तिशाली, विशेषकर भगवान कृष्ण के लिए। उपवास और आध्यात्मिक प्रथाओं के लिए अच्छा। अत्यधिक भौतिकवाद और इंद्रिय सुखों से बचें।",
        "Favorable for protective measures and strengthening security. Good for courage and determination. Avoid unnecessary risks and fears.": "सुरक्षात्मक उपायों और सुरक्षा मजबूत करने के लिए अनुकूल। साहस और दृढ़ता के लिए अच्छा। अनावश्यक जोखिमों और डर से बचें।",
        "Good for ethical decisions and righteous actions. Favorable for legal matters. Avoid dishonesty and unethical compromises.": "नैतिक निर्णयों और धर्म के कार्यों के लिए अच्छा। कानूनी मामलों के लिए अनुकूल। बेईमानी और अनैतिक समझौतों से बचें।",
        "Highly auspicious for fasting and spiritual practices. Good for detachment and self-control. Avoid overindulgence and material attachment.": "उपवास और आध्यात्मिक प्रथाओं के लिए अत्यधिक शुभ। अनासक्ति और आत्म-नियंत्रण के लिए अच्छा। अति और भौतिक लगाव से बचें।",
        "Favorable for breaking fasts and charitable activities. Good for generosity and giving. Avoid starting new projects and major decisions.": "उपवास तोड़ने और दान की गतिविधियों के लिए अनुकूल। उदारता और देने के लिए अच्छा। नई परियोजनाएं शुरू करने और बड़े निर्णयों से बचें।",
        "Powerful for spiritual practices, especially those related to transformation. Good for overcoming challenges. Avoid fear and negative thinking.": "आध्यात्मिक प्रथाओं के लिए शक्तिशाली, विशेषकर परिवर्तन से संबंधित। चुनौतियों पर काबू पाने के लिए अच्छा। डर और नकारात्मक सोच से बचें।",
        "Suitable for removing obstacles and ending negative influences. Good for spiritual cleansing. Avoid dark places and negative company.": "बाधाओं को दूर करने और नकारात्मक प्रभावों को समाप्त करने के लिए उपयुक्त। आध्यात्मिक शुद्धीकरण के लिए अच्छा। अंधेरी जगहों और नकारात्मक संगति से बचें।",
        "Powerful for ancestral worship and ending karmic cycles. Good for meditation and inner work. Avoid major beginnings and public activities.": "पूर्वजों की पूजा और कर्म चक्रों को समाप्त करने के लिए शक्तिशाली। ध्यान और आंतरिक कार्य के लिए अच्छा। बड़ी शुरुआत और सार्वजनिक गतिविधियों से बचें।",
        
        #NAKSHTRA
        "Mrigashira is ruled by Mars and presided over by Soma. Symbolized by a deer's head, it represents the searching, gentle qualities of exploration and discovery. People born under this nakshatra are often curious, adaptable, and possess excellent communication skills. They have a natural ability to seek out knowledge and opportunities. Mrigashira supports research, exploration, communication-based ventures, travel, and pursuits requiring both gentleness and persistence.": "मृगशिरा मंगळ द्वारा शासित और सोम से संबंधित है। यह खोज, कोमलता और अन्वेषण का प्रतीक है। इस नक्षत्र के जातक जिज्ञासु, लचीले और अच्छे संवादकर्ता होते हैं। यह नक्षत्र यात्रा, खोज, अनुसंधान और संप्रेषण से जुड़े कार्यों के लिए उपयुक्त है।",

        "Ashwini is symbolized by a horse's head and ruled by Ketu. People born under this nakshatra are often quick, energetic, and enthusiastic. They excel in competitive environments, possess natural healing abilities, and have a strong desire for recognition. Ashwini brings qualities of intelligence, charm, and restlessness, making natives good at starting new ventures but sometimes impatient. It's auspicious for medical pursuits, transportation, sports, and quick endeavors.": "अश्विनी नक्षत्र का प्रतीक घोड़े का सिर है और यह केतु द्वारा शासित है। इस नक्षत्र में जन्मे व्यक्ति तीव्र, ऊर्जावान और उत्साही होते हैं। ये लोग प्रतिस्पर्धी वातावरण में उत्कृष्ट प्रदर्शन करते हैं, स्वाभाविक उपचार क्षमता रखते हैं और पहचान की तीव्र इच्छा रखते हैं। यह नक्षत्र चिकित्सा, यात्रा, खेल और शीघ्र आरंभ होने वाले कार्यों के लिए शुभ है।",

        "Bharani is ruled by Venus and presided over by Yama, the god of death. This nakshatra represents the cycle of creation, maintenance, and dissolution. Bharani natives are often disciplined, determined, and possess strong creative energies. They excel in transforming circumstances and handling resources. This nakshatra supports activities related to cultivation, growth processes, financial management, and endeavors requiring perseverance and discipline.": "भरणी नक्षत्र शुक्र के अधीन है और यम देवता द्वारा शासित है। यह सृजन, पालन और संहार के चक्र का प्रतिनिधित्व करता है। भरणी में जन्मे व्यक्ति अनुशासित, दृढ़ इच्छाशक्ति वाले और रचनात्मक ऊर्जा से भरपूर होते हैं। यह नक्षत्र कृषि, वित्तीय प्रबंधन, दीर्घकालिक योजनाओं और कठिन परिश्रम की मांग करने वाले कार्यों के लिए उपयुक्त है।",

        "Krittika is ruled by the Sun and associated with Agni, the fire god. People born under this nakshatra often possess sharp intellect, strong ambition, and purifying energy. They can be brilliant, focused, and passionate about their pursuits. Krittika is favorable for activities requiring purification, leadership roles, analytical work, and transformative processes. Its energy supports clarity, precision, and the burning away of obstacles.": "कृत्तिका नक्षत्र सूर्य द्वारा शासित होता है और अग्नि देवता से जुड़ा होता है। इस नक्षत्र के जातक तेज बुद्धि, तीव्र इच्छा शक्ति और शुद्ध करने वाली ऊर्जा से युक्त होते हैं। यह नक्षत्र नेतृत्व, विश्लेषणात्मक कार्यों, और परिवर्तनात्मक प्रक्रियाओं के लिए शुभ है।",

        "Rohini is ruled by the Moon and associated with Lord Brahma. This nakshatra represents growth, nourishment, and material abundance. Natives of Rohini are often creative, sensual, and possess natural artistic talents. They value stability, beauty, and comfort. This nakshatra is excellent for activities related to agriculture, artistic pursuits, luxury industries, stable relationships, and endeavors requiring patience and sustained effort.": "रोहिणी नक्षत्र चंद्र द्वारा शासित होता है और ब्रह्मा से जुड़ा होता है। यह समृद्धि, पोषण, और सौंदर्य का प्रतीक है। रोहिणी जातक कलात्मक, स्थिरता प्रेमी और आकर्षणशील होते हैं। यह नक्षत्र कृषि, कला, लक्ज़री और दीर्घकालिक योजनाओं के लिए शुभ होता है।",

        "Mrigashira is ruled by Mars and presided over by Soma. Symbolized by a deer's head, it represents the searching, gentle qualities of exploration and discovery. People born under this nakshatra are often curious, adaptable, and possess excellent communication skills. They have a natural ability to seek out knowledge and opportunities. Mrigashira supports research, exploration, communication-based ventures, travel, and pursuits requiring both gentleness and persistence.": "मृगशिरा मंगळ द्वारा शासित और सोम से संबंधित है। यह खोज, कोमलता और अन्वेषण का प्रतीक है। इस नक्षत्र के जातक जिज्ञासु, लचीले और अच्छे संवादकर्ता होते हैं। यह नक्षत्र यात्रा, खोज, अनुसंधान और संप्रेषण से जुड़े कार्यों के लिए उपयुक्त है।",

        "Ardra is ruled by Rahu and associated with Rudra, the storm god. This powerful nakshatra represents transformation through intensity and challenge. Ardra natives often possess strong emotional depth, persistence through difficulties, and regenerative capabilities. They can be passionate, determined, and unafraid of life's storms. This nakshatra supports endeavors requiring breaking through obstacles, profound change, crisis management, and transformative healing.": "आर्द्रा नक्षत्र राहु द्वारा शासित होता है और रुद्र से संबंधित होता है। यह परिवर्तन, तीव्र भावना और संघर्ष की क्षमता का प्रतीक है। आर्द्रा के जातक संवेदनशील, जिज्ञासु और परिवर्तनशील होते हैं। यह चिकित्सा, अनुसंधान, और तीव्र परिवर्तन वाले कार्यों के लिए अनुकूल है।",
        
        "Punarvasu is ruled by Jupiter and presided over by Aditi, goddess of boundlessness. This nakshatra represents renewal, return to wealth, and expansive growth. People born under Punarvasu often possess natural wisdom, generosity, and optimistic outlook. They excel at bringing renewal to situations and seeing the broader perspective. This nakshatra supports education, spiritual pursuits, teaching, counseling, and ventures requiring wisdom, renewal, and positive growth.": "पुनर्वसु नक्षत्र बृहस्पति द्वारा शासित है और अदिति देवी से जुड़ा है। यह पुनरावृत्ति, आशावाद और आध्यात्मिक ज्ञान का प्रतीक है। जातक उदार, ज्ञानशील और सहनशील होते हैं। शिक्षा, परामर्श, और सकारात्मक परिवर्तन के लिए यह नक्षत्र शुभ होता है।",

        "Pushya is ruled by Saturn and associated with Brihaspati. Considered one of the most auspicious nakshatras, it represents nourishment, prosperity, and spiritual abundance. Pushya natives are often nurturing, responsible, and possess strong moral values. They excel at creating stability and growth. This nakshatra is excellent for beginning important ventures, spiritual practices, charitable work, healing professions, and endeavors requiring integrity, nourishment, and sustained positive growth.":" पुष्य नक्षत्र शनि द्वारा शासित है और बृहस्पति से जुड़ा है। इसे सबसे शुभ नक्षत्रों में से एक माना जाता है। यह पोषण, समृद्धि और आध्यात्मिक प्रचुरता का प्रतीक है। पुष्य जातक nurturing, जिम्मेदार और नैतिक मूल्यों वाले होते हैं। यह नक्षत्र महत्वपूर्ण कार्यों की शुरुआत, आध्यात्मिक प्रथाओं, दान कार्यों और चिकित्सा व्यवसायों के लिए शुभ होता है।",

        "Ashlesha is ruled by Mercury and presided over by the Nagas. Symbolized by a coiled serpent, it represents kundalini energy, mystical knowledge, and penetrating insight. People born under this nakshatra often possess strong intuition, healing abilities, and magnetic personality. They have natural investigative skills and understand hidden matters. Ashlesha supports medical research, psychological work, occult studies, and endeavors requiring penetrating intelligence and transformative power.":" अश्लेषा नक्षत्र बुध द्वारा शासित है और नागों से संबंधित है। यह कुंडलिनी ऊर्जा, रहस्यमय ज्ञान और गहरी अंतर्दृष्टि का प्रतीक है। इस नक्षत्र के जातक तीव्र अंतर्ज्ञान, उपचार क्षमता और आकर्षक व्यक्तित्व के स्वामी होते हैं। यह नक्षत्र चिकित्सा अनुसंधान, मनोवैज्ञानिक कार्य, और गूढ़ अध्ययन के लिए उपयुक्त है।",

        "Magha is ruled by Ketu and associated with the Pitris, or ancestral spirits. This nakshatra represents power, leadership, and ancestral connections. Magha natives often possess natural authority, dignity, and a sense of duty to their lineage. They value honor and recognition. This nakshatra supports leadership roles, governmental work, ancestral healing, ceremonial activities, and ventures requiring public recognition, authority, and connection to tradition and heritage.":" मघा नक्षत्र केतु द्वारा शासित है और पितरों से संबंधित है। यह शक्ति, नेतृत्व और पूर्वजों के संबंध का प्रतीक है। मघा जातक स्वाभाविक अधिकार, गरिमा और अपने वंश के प्रति कर्तव्यबद्ध होते हैं। यह नक्षत्र नेतृत्व, सरकारी कार्य, पूर्वजों की चिकित्सा, और परंपरा से जुड़े कार्यों के लिए शुभ होता है.",

        "Purva Phalguni is ruled by Venus and presided over by Bhaga, god of enjoyment. This nakshatra represents creative expression, pleasure, and social harmony. People born under this nakshatra often possess charm, creativity, and natural social skills. They enjoy beauty and relationships. Purva Phalguni supports artistic endeavors, romance, entertainment, social activities, and ventures requiring creativity, pleasure, and harmonious social connections.": "पूर्व फाल्गुनी नक्षत्र शुक्र द्वारा शासित है और भोग के देवता भागा से संबंधित है। यह रचनात्मक अभिव्यक्ति, आनंद और सामाजिक सामंजस्य का प्रतीक है। पूर्व फाल्गुनी जातक आकर्षण, रचनात्मकता और सामाजिक कौशल के स्वामी होते हैं। यह नक्षत्र कलात्मक प्रयासों, रोमांस, मनोरंजन, और सामाजिक गतिविधियों के लिए शुभ होता है.",

        "Uttara Phalguni is ruled by the Sun and presided over by Aryaman, god of contracts and patronage. This nakshatra represents harmonious social relationships, beneficial agreements, and balanced partnerships. Natives of this nakshatra often value fairness, social harmony, and mutually beneficial relationships. They possess natural diplomatic abilities. This nakshatra supports marriage, contracts, partnerships, social networking, and endeavors requiring balance, integrity, and harmonious cooperation.":"उत्तर फाल्गुनी नक्षत्र सूर्य द्वारा शासित है और अनुबंधों और संरक्षकता के देवता आर्यमन से संबंधित है। यह सामंजस्यपूर्ण सामाजिक संबंध, लाभकारी समझौते, और संतुलित साझेदारियों का प्रतीक है। उत्तर फाल्गुनी जातक निष्पक्षता, सामाजिक सामंजस्य, और आपसी लाभकारी संबंधों को महत्व देते हैं। यह नक्षत्र विवाह, अनुबंध, साझेदारी, और सामाजिक नेटवर्किंग के लिए शुभ होता है.",

        "Hasta is ruled by the Moon and presided over by Savitar. Symbolized by a hand, this nakshatra represents practical skills, craftsmanship, and manifesting ability. People born under Hasta often possess excellent manual dexterity, practical intelligence, and healing abilities. They excel at bringing ideas into form. This nakshatra supports craftsmanship, healing work, practical skills development, technological endeavors, and activities requiring precision, skill, and the ability to manifest ideas into reality.": "हस्त नक्षत्र चंद्र द्वारा शासित है और सविता से संबंधित है। यह व्यावहारिक कौशल, शिल्प कौशल, और साकारात्मक क्षमता का प्रतीक है। हस्त जातक उत्कृष्ट मैनुअल दक्षता, व्यावहारिक बुद्धिमत्ता, और उपचार क्षमता के स्वामी होते हैं। यह नक्षत्र शिल्पकला, चिकित्सा कार्य, व्यावहारिक कौशल विकास, और प्रौद्योगिकी के लिए शुभ होता है.",

        "Chitra is ruled by Mars and associated with Vishvakarma, the divine architect. This nakshatra represents creative design, multi-faceted brilliance, and artistic excellence. Chitra natives often possess diverse talents, creative vision, and appreciation for beauty and design. They tend to stand out in whatever they do. This nakshatra supports design work, architecture, fashion, arts, strategic planning, and endeavors requiring creative brilliance, versatility, and visual excellence.": "चित्र नक्षत्र मंगळ द्वारा शासित है और विश्वकर्मा, दिव्य वास्तुकार से संबंधित है। यह रचनात्मक डिज़ाइन, बहुआयामी प्रतिभा, और कलात्मक उत्कृष्टता का प्रतीक है। चित्र जातक विविध प्रतिभाओं, रचनात्मक दृष्टि, और सौंदर्य और डिज़ाइन की सराहना के स्वामी होते हैं। यह नक्षत्र डिज़ाइन कार्य, वास्तुकला, फैशन, कला, और रणनीतिक योजना के लिए शुभ होता है.",

        "Swati is ruled by Rahu and presided over by Vayu, god of wind. This nakshatra represents independent movement, self-sufficiency, and scattered brilliance. People born under Swati often possess adaptability, independent thinking, and movement-oriented talents. They value freedom and have an unpredictable quality. This nakshatra supports independent ventures, travel, aviation, communication, and endeavors requiring adaptability, independence, and the ability to spread ideas widely.": "स्वाति नक्षत्र राहु द्वारा शासित है और वायु देवता से संबंधित है। यह स्वतंत्र आंदोलन, आत्मनिर्भरता, और बिखरी हुई प्रतिभा का प्रतीक है। स्वाति जातक लचीले, स्वतंत्र विचारक, और आंदोलन-उन्मुख प्रतिभाओं के स्वामी होते हैं। यह नक्षत्र स्वतंत्र उद्यमों, यात्रा, विमानन, संचार, और लचीलेपन की मांग करने वाले कार्यों के लिए शुभ होता है.",

        "Vishakha is ruled by Jupiter and associated with Indra-Agni. This nakshatra represents focused determination, purposeful effort, and achievement of goals. Vishakha natives are often ambitious, determined, and possess leadership qualities combined with spiritual focus. They excel at achieving objectives through sustained effort. This nakshatra supports goal-setting, leadership roles, competitive activities, spiritual pursuits with practical aims, and endeavors requiring determination, focus, and strategic achievement.": "विशाखा नक्षत्र गुरु द्वारा शासित है और इंद्र-आग्नि से संबंधित है। यह केंद्रित संकल्प, उद्देश्यपूर्ण प्रयास, और लक्ष्यों की प्राप्ति का प्रतीक है। विशाखा जातक अक्सर महत्वाकांक्षी, दृढ़ निश्चयी होते हैं, और आध्यात्मिक ध्यान के साथ नेतृत्व गुणों के स्वामी होते हैं। यह नक्षत्र लक्ष्यों को प्राप्त करने के लिए निरंतर प्रयास का समर्थन करता है।",

        "Anuradha is ruled by Saturn and presided over by Mitra, god of friendship. This nakshatra represents successful cooperation, friendship, and devotion. People born under Anuradha often possess natural diplomatic skills, loyalty, and ability to succeed through harmonious relationships. They value friendship and cooperation. This nakshatra supports teamwork, diplomatic endeavors, friendship-based ventures, devotional practices, and activities requiring cooperation, loyalty, and mutual success.": "अनुराधा नक्षत्र शनि द्वारा शासित है और मित्र देवता द्वारा शासित है। यह सफल सहयोग, मित्रता, और भक्ति का प्रतीक है। अनुराधा जातक स्वाभाविक कूटनीतिक कौशल, वफादारी, और सामंजस्यपूर्ण संबंधों के माध्यम से सफलता प्राप्त करने की क्षमता के स्वामी होते हैं। यह नक्षत्र टीमवर्क, कूटनीतिक प्रयासों, मित्रता-आधारित उद्यमों, भक्ति प्रथाओं, और सहयोग की मांग करने वाले कार्यों के लिए शुभ होता है.",

        "Jyeshtha is ruled by Mercury and associated with Indra, king of the gods. This nakshatra represents seniority, protective leadership, and courage. Jyeshtha natives often possess natural leadership abilities, protective instincts, and desire for recognition. They have strong personalities and sense of authority. This nakshatra supports leadership roles, protective services, senior positions, mentorship, and endeavors requiring courage, protection of others, and the wielding of authority with intelligence.":"ज्येष्ठ नक्षत्र बुध द्वारा शासित है और देवताओं के राजा इंद्र से संबंधित है। यह वरिष्ठता, संरक्षक नेतृत्व, और साहस का प्रतीक है। ज्येष्ठ जातक स्वाभाविक नेतृत्व क्षमताओं, संरक्षक प्रवृत्तियों, और मान्यता की इच्छा के स्वामी होते हैं। यह नक्षत्र नेतृत्व भूमिकाओं, संरक्षक सेवाओं, वरिष्ठ पदों, मार्गदर्शन, और साहस की मांग करने वाले कार्यों के लिए शुभ होता है.",

        "Mula is ruled by Ketu and presided over by Nirriti. Its name means 'root' and it represents the destructive power that precedes creation. People born under Mula often possess investigative abilities, interest in fundamental principles, and transformative energy. They can get to the root of matters. This nakshatra supports research, elimination of obstacles, fundamental change, spiritual pursuits, and endeavors requiring deep investigation, uprooting of problems, and complete transformation.": "मूल नक्षत्र केतु द्वारा शासित है और निरृति द्वारा शासित है। इसका नाम 'जड़' का अर्थ है और यह सृजन से पहले की विनाशकारी शक्ति का प्रतीक है। मूल जातक अनुसंधान क्षमताओं, मौलिक सिद्धांतों में रुचि, और परिवर्तनकारी ऊर्जा के स्वामी होते हैं। यह नक्षत्र अनुसंधान, बाधाओं को समाप्त करने, मौलिक परिवर्तन, आध्यात्मिक प्रयासों, और गहरी जांच की मांग करने वाले कार्यों के लिए शुभ होता है.",

        "Purva Ashadha is ruled by Venus and associated with Apas, the water goddesses. This nakshatra represents early victory, invigoration, and unquenchable energy. Purva Ashadha natives often possess determination, enthusiasm, and ability to overcome obstacles through sustained effort. They have purifying energy and natural leadership. This nakshatra supports initial phases of important projects, leadership roles, water-related activities, and endeavors requiring determination, purification, and invincible enthusiasm.": "पूर्व अशाढ़ नक्षत्र शुक्र द्वारा शासित है और अपस, जल देवियों से संबंधित है। यह प्रारंभिक विजय, उत्साह, और अविराम ऊर्जा का प्रतीक है। पूर्व अशाढ़ जातक दृढ़ संकल्प, उत्साह, और निरंतर प्रयास के माध्यम से बाधाओं को पार करने की क्षमता के स्वामी होते हैं। यह नक्षत्र महत्वपूर्ण परियोजनाओं के प्रारंभिक चरणों, नेतृत्व भूमिकाओं, जल संबंधी गतिविधियों, और दृढ़ संकल्प, शुद्धिकरण, और अजेय उत्साह की मांग करने वाले कार्यों के लिए शुभ होता है.",

        "Uttara Ashadha is ruled by the Sun and presided over by the Vishvedevas. This nakshatra represents later victory, universal principles, and balanced power. People born under this nakshatra often possess strong principles, balanced leadership abilities, and capacity for enduring success. They value universal truths and lasting achievement. This nakshatra supports long-term projects, ethical leadership, philosophical pursuits, and endeavors requiring principled action, balanced power, and sustained, honorable success.": "उत्तर अशाढ़ नक्षत्र सूर्य द्वारा शासित है और विश्वेदेवों द्वारा शासित है। यह बाद की विजय, सार्वभौमिक सिद्धांत, और संतुलित शक्ति का प्रतीक है। उत्तर अशाढ़ जातक मजबूत सिद्धांतों, संतुलित नेतृत्व क्षमताओं, और स्थायी सफलता की क्षमता के स्वामी होते हैं। यह नक्षत्र दीर्घकालिक परियोजनाओं, नैतिक नेतृत्व, दार्शनिक प्रयासों, और सिद्धांतबद्ध क्रिया, संतुलित शक्ति, और सम्मानजनक सफलता की मांग करने वाले कार्यों के लिए शुभ होता है.",

        "Shravana is ruled by the Moon and associated with Lord Vishnu. Its name relates to hearing and it represents learning through listening, connectivity, and devotion. Shravana natives often possess excellent listening skills, learning abilities, and connective intelligence. They value wisdom and harmonious relationships. This nakshatra supports education, communication, devotional practices, networking, and endeavors requiring good listening, wisdom gathering, connectivity, and the harmonizing of diverse elements.": "श्रवण नक्षत्र चंद्र द्वारा शासित है और भगवान विष्णु से संबंधित है। इसका नाम सुनने से संबंधित है और यह सुनने के माध्यम से सीखने, कनेक्टिविटी, और भक्ति का प्रतीक है। श्रवण जातक उत्कृष्ट सुनने की क्षमताओं, सीखने की क्षमताओं, और कनेक्टिव बुद्धिमत्ता के स्वामी होते हैं। यह नक्षत्र शिक्षा, संचार, भक्ति प्रथाओं, नेटवर्किंग, और अच्छे सुनने, ज्ञान संग्रहण, कनेक्टिविटी, और विविध तत्वों के सामंजस्य की मांग करने वाले कार्यों के लिए शुभ होता है.",

        "Dhanishta is ruled by Mars and presided over by the Vasus. This nakshatra represents wealth, rhythm, music, and generous abundance. People born under Dhanishta often possess musical talents, rhythmic abilities, and natural generosity. They have a prosperous energy and ability to create wealth. This nakshatra supports musical endeavors, wealth creation, philanthropic activities, and ventures requiring rhythm, momentum, prosperous energy, and the generous sharing of abundance.": "धनिष्ठा नक्षत्र मंगल द्वारा शासित है और वासु देवताओं द्वारा शासित है। यह धन, लय, संगीत, और उदार प्रचुरता का प्रतीक है। धनिष्ठा जातक स्वाभाविक संगीत प्रतिभाओं, लयात्मक क्षमताओं, और प्राकृतिक उदारता के स्वामी होते हैं। यह नक्षत्र संगीत प्रयासों, धन सृजन, परोपकारी गतिविधियों, और लय, गति, समृद्ध ऊर्जा, और प्रचुरता के उदार साझा करने की मांग करने वाले उद्यमों के लिए शुभ होता है.",

        "Shatabhisha is ruled by Rahu and associated with Varuna. Its name means 'hundred healers' and it represents healing powers, scientific understanding, and cosmic awareness. Shatabhisha natives often possess innovative thinking, healing abilities, and independent perspective. They can perceive beyond conventional boundaries. This nakshatra supports medical practices, scientific research, alternative healing, mystical pursuits, and endeavors requiring innovation, independence of thought, and broad awareness of interconnected systems.": "शतभिषक नक्षत्र राहु द्वारा शासित है और वरुण से संबंधित है। इसका नाम 'सौ चिकित्सक' का अर्थ है और यह चिकित्सा शक्तियों, वैज्ञानिक समझ, और ब्रह्मांडीय जागरूकता का प्रतीक है। शतभिषक जातक नवोन्मेषी सोच, चिकित्सा क्षमताओं, और स्वतंत्र दृष्टिकोण के स्वामी होते हैं। यह नक्षत्र चिकित्सा प्रथाओं, वैज्ञानिक अनुसंधान, वैकल्पिक चिकित्सा, और गूढ़ प्रयासों के लिए शुभ होता है.",

        "Purva Bhadrapada is ruled by Jupiter and presided over by Aja Ekapada. This nakshatra represents fiery wisdom, intensity, and spiritual awakening through challenge. People born under this nakshatra often possess penetrating insight, transformative vision, and ability to inspire others. They can be intensely focused on their path. This nakshatra supports spiritual pursuits, inspirational leadership, transformative teaching, and endeavors requiring intensity, deep wisdom, and the courage to walk a unique spiritual path.": "पूर्व भद्रपद नक्षत्र गुरु द्वारा शासित है और अजा एकपद द्वारा शासित है। यह अग्निमय ज्ञान, तीव्रता, और चुनौती के माध्यम से आध्यात्मिक जागरूकता का प्रतीक है। पूर्व भद्रपद जातक गहन अंतर्दृष्टि, परिवर्तनकारी दृष्टि, और दूसरों को प्रेरित करने की क्षमता के स्वामी होते हैं। यह नक्षत्र आध्यात्मिक प्रयासों, प्रेरणादायक नेतृत्व, परिवर्तनकारी शिक्षण, और तीव्रता, गहरे ज्ञान, और एक अद्वितीय आध्यात्मिक पथ पर चलने के साहस की मांग करने वाले कार्यों के लिए शुभ होता है।",

        "Uttara Bhadrapada is ruled by Saturn and associated with Ahirbudhnya. This nakshatra represents deep truth, serpentine wisdom, and regenerative power from the depths. Uttara Bhadrapada natives often possess profound understanding, regenerative abilities, and capacity to bring hidden truths to light. They value depth and authenticity. This nakshatra supports deep research, psychological work, spiritual transformation, and endeavors requiring profound wisdom, regenerative power, and the ability to work with hidden forces.": "उत्तर भद्रपद नक्षत्र शनि द्वारा शासित है और अहिरबुध्न्य से संबंधित है। यह गहरी सच्चाई, सर्पिल ज्ञान, और गहराई से पुनर्जनन शक्ति का प्रतीक है। उत्तर भद्रपद जातक गहन समझ, पुनर्जनन क्षमताओं, और छिपी हुई सच्चाइयों को उजागर करने की क्षमता के स्वामी होते हैं। यह नक्षत्र गहन अनुसंधान, मनोवैज्ञानिक कार्य, आध्यात्मिक परिवर्तन, और गहरे ज्ञान, पुनर्जनन शक्ति, और छिपी हुई शक्तियों के साथ काम करने की क्षमता की मांग करने वाले कार्यों के लिए शुभ होता है।",

        "Revati is ruled by Mercury and presided over by Pushan. As the final nakshatra, it represents completion, nourishment, and protection during transitions. People born under Revati often possess nurturing qualities, protective wisdom, and ability to nourish others across transitions. They tend to be caring and supportive. This nakshatra supports completion of cycles, nurturing activities, transitional guidance, and endeavors requiring gentle wisdom, nourishing qualities, and the ability to help others move smoothly through life's transitions.": "रेवती नक्षत्र बुध द्वारा शासित है और पुषन द्वारा शासित है। अंतिम नक्षत्र के रूप में, यह पूर्णता, पोषण, और संक्रमण के दौरान सुरक्षा का प्रतीक है। रेवती जातक पोषण गुणों, संरक्षक ज्ञान, और संक्रमण के दौरान दूसरों को पोषित करने की क्षमता के स्वामी होते हैं। यह नक्षत्र चक्रों की पूर्णता, पोषण गतिविधियों, संक्रमण संबंधी मार्गदर्शन, और कोमल ज्ञान, पोषण गुणों, और दूसरों को जीवन के संक्रमणों के माध्यम से सुचारू रूप से आगे बढ़ने में मदद करने की क्षमता की मांग करने वाले कार्यों के लिए शुभ होता है.",

        # Yoga meanings
"Pillar or Support": "स्तंभ या सहारा",
"Love and Joy": "प्रेम और आनंद",
"Longevity and Health": "दीर्घायु और स्वास्थ्य",
"Good Fortune and Prosperity": "सौभाग्य और समृद्धि",
"Beauty and Splendor": "सुंदरता और वैभव",
"Extreme Danger": "अत्यधिक खतरा",
"Good Action": "शुभ कर्म",
"Steadiness and Determination": "स्थिरता और दृढ़ता",
"Spear or Pain": "भाला या पीड़ा",
"Obstacle or Problem": "बाधा या समस्या",
"Growth and Prosperity": "वृद्धि और समृद्धि",
"Fixed and Permanent": "स्थिर और स्थायी",
"Obstruction or Danger": "बाधा या खतरा",
"Joy and Happiness": "खुशी और आनंद",
"Thunderbolt or Diamond": "वज्र या हीरा",
"Success and Accomplishment": "सफलता और उपलब्धि",
"Calamity or Disaster": "विपत्ति या आपदा",
"Superior or Excellent": "श्रेष्ठ या उत्कृष्ट",
"Obstacle or Hindrance": "बाधा या रुकावट",
"Auspicious and Beneficial": "शुभ और लाभकारी",
"Accomplished or Perfected": "पूर्ण या सिद्ध",
"Accomplishable or Achievable": "प्राप्त करने योग्य",
"Auspicious and Fortunate": "शुभ और भाग्यशाली",
"Bright and Pure": "उज्ज्वल और शुद्ध",
"Creative and Divine": "रचनात्मक और दिव्य",
"Leadership and Power": "नेतृत्व और शक्ति",
"Separation or Division": "विभाजन या अलगाव",

# Yoga specialities
"Obstacles, challenges that lead to strength": "बाधाएं, चुनौतियां जो शक्ति की ओर ले जाती हैं",
"Excellent for relationships and pleasant activities": "रिश्तों और सुखद गतिविधियों के लिए उत्कृष्ट",
"Good for medical treatments and health initiatives": "चिकित्सा उपचार और स्वास्थ्य पहलों के लिए अच्छा",
"Auspicious for financial matters and prosperity": "वित्तीय मामलों और समृद्धि के लिए शुभ",
"Favorable for artistic pursuits and aesthetics": "कलात्मक गतिविधियों और सौंदर्यशास्त्र के लिए अनुकूल",
"Challenging; best for cautious and reflective activities": "चुनौतीपूर्ण; सावधान और चिंतनशील गतिविधियों के लिए सर्वोत्तम",
"Excellent for all virtuous and important actions": "सभी सद्गुणों और महत्वपूर्ण कार्यों के लिए उत्कृष्ट",
"Good for activities requiring persistence and stability": "दृढ़ता और स्थिरता की आवश्यकता वाली गतिविधियों के लिए अच्छा",
"Challenging; good for decisive and courageous actions": "चुनौतीपूर्ण; निर्णायक और साहसी कार्यों के लिए अच्छा",
"Difficult; best for solving problems and removing obstacles": "कठिन; समस्याओं को हल करने और बाधाओं को दूर करने के लिए सर्वोत्तम",
"Excellent for growth-oriented activities and investments": "विकास-उन्मुख गतिविधियों और निवेश के लिए उत्कृष्ट",
"Good for activities requiring stability and endurance": "स्थिरता और सहनशीलता की आवश्यकता वाली गतिविधियों के लिए अच्छा",
"Challenging; requires careful planning and execution": "चुनौतीपूर्ण; सावधानीपूर्वक योजना और निष्पादन की आवश्यकता",
"Favorable for celebrations and enjoyable activities": "उत्सव और आनंददायक गतिविधियों के लिए अनुकूल",
"Powerful but unstable; good for forceful actions": "शक्तिशाली लेकिन अस्थिर; बलपूर्वक कार्यों के लिए अच्छा",
"Highly auspicious for all important undertakings": "सभी महत्वपूर्ण कार्यों के लिए अत्यधिक शुभ",
"Challenging; best for spiritual practices and caution": "चुनौतीपूर्ण; आध्यात्मिक प्रथाओं और सावधानी के लिए सर्वोत्तम",
"Good for bold actions and leadership initiatives": "साहसिक कार्यों और नेतृत्व पहलों के लिए अच्छा",
"Difficult; better for routine activities and patience": "कठिन; नियमित गतिविधियों और धैर्य के लिए बेहतर",
"Excellent for all positive and important undertakings": "सभी सकारात्मक और महत्वपूर्ण कार्यों के लिए उत्कृष्ट",
"Highly favorable for all significant activities": "सभी महत्वपूर्ण गतिविधियों के लिए अत्यधिक अनुकूल",
"Good for activities that can be completed quickly": "जल्दी पूरी होने वाली गतिविधियों के लिए अच्छा",
"Excellent for all auspicious and important activities": "सभी शुभ और महत्वपूर्ण गतिविधियों के लिए उत्कृष्ट",
"Favorable for spirituality and pure intentions": "आध्यात्मिकता और शुद्ध इरादों के लिए अनुकूल",
"Excellent for creative pursuits and spiritual activities": "रचनात्मक गतिविधियों और आध्यात्मिक गतिविधियों के लिए उत्कृष्ट",
"Good for leadership activities and positions of authority": "नेतृत्व गतिविधियों और अधिकार के पदों के लिए अच्छा",
"Challenging; best for contemplation and careful planning": "चुनौतीपूर्ण; चिंतन और सावधानीपूर्वक योजना के लिए सर्वोत्तम",

    },

    "gujarati": {

        # Yoga meanings
"Pillar or Support": "સ્તંભ અથવા આધાર",
"Love and Joy": "પ્રેમ અને આનંદ",
"Longevity and Health": "દીર્ઘાયુ અને આરોગ્ય",
"Good Fortune and Prosperity": "સૌભાગ્ય અને સમૃદ્ધિ",
"Beauty and Splendor": "સૌંદર્ય અને વૈભવ",
"Extreme Danger": "અત્યંત ખતરો",
"Good Action": "શુભ કર્મ",
"Steadiness and Determination": "સ્થિરતા અને દૃઢતા",
"Spear or Pain": "ભાલો અથવા પીડા",
"Obstacle or Problem": "અવરોધ અથવા સમસ્યા",
"Growth and Prosperity": "વૃદ્ધિ અને સમૃદ્ધિ",
"Fixed and Permanent": "સ્થિર અને કાયમી",
"Obstruction or Danger": "અવરોધ અથવા ખતરો",
"Joy and Happiness": "આનંદ અને ખુશી",
"Thunderbolt or Diamond": "વજ્ર અથવા હીરો",
"Success and Accomplishment": "સફળતા અને સિદ્ધિ",
"Calamity or Disaster": "આફત અથવા આપત્તિ",
"Superior or Excellent": "શ્રેષ્ઠ અથવા ઉત્કૃષ્ટ",
"Obstacle or Hindrance": "અવરોધ અથવા અટકાવો",
"Auspicious and Beneficial": "શુભ અને લાભકારી",
"Accomplished or Perfected": "પૂર્ણ અથવા સિદ્ધ",
"Accomplishable or Achievable": "પ્રાપ્ત કરી શકાય તેવું",
"Auspicious and Fortunate": "શુભ અને ભાગ્યશાળી",
"Bright and Pure": "તેજસ્વી અને શુદ્ધ",
"Creative and Divine": "સર્જનાત્મક અને દિવ્ય",
"Leadership and Power": "નેતૃત્વ અને શક્તિ",
"Separation or Division": "વિભાજન અથવા અલગાવ",

# Yoga specialities
"Obstacles, challenges that lead to strength": "અવરોધો, પડકારો જે શક્તિ તરફ દોરી જાય છે",
"Excellent for relationships and pleasant activities": "સંબંધો અને સુખદ પ્રવૃત્તિઓ માટે ઉત્કૃષ્ટ",
"Good for medical treatments and health initiatives": "તબીબી સારવાર અને આરોગ્ય પહેલો માટે સારું",
"Auspicious for financial matters and prosperity": "નાણાકીય બાબતો અને સમૃદ્ધિ માટે શુભ",
"Favorable for artistic pursuits and aesthetics": "કલાત્મક પ્રવૃત્તિઓ અને સૌંદર્યશાસ્ત્ર માટે અનુકૂળ",
"Challenging; best for cautious and reflective activities": "પડકારજનક; સાવધ અને ચિંતનશીલ પ્રવૃત્તિઓ માટે શ્રેષ્ઠ",
"Excellent for all virtuous and important actions": "બધા સદગુણ અને મહત્વપૂર્ણ કર્મો માટે ઉત્કૃષ્ટ",
"Good for activities requiring persistence and stability": "દૃઢતા અને સ્થિરતાની જરૂર પડતી પ્રવૃત્તિઓ માટે સારું",
"Challenging; good for decisive and courageous actions": "પડકારજનક; નિર્ણાયક અને સાહસિક કર્મો માટે સારું",
"Difficult; best for solving problems and removing obstacles": "કઠિન; સમસ્યાઓ હલ કરવા અને અવરોધો દૂર કરવા માટે શ્રેષ્ઠ",
"Excellent for growth-oriented activities and investments": "વિકાસ-લક્ષી પ્રવૃત્તિઓ અને રોકાણ માટે ઉત્કૃષ્ટ",
"Good for activities requiring stability and endurance": "સ્થિરતા અને સહનશીલતાની જરૂર પડતી પ્રવૃત્તિઓ માટે સારું",
"Challenging; requires careful planning and execution": "પડકારજનક; સાવધ આયોજન અને અમલીકરણની જરૂર",
"Favorable for celebrations and enjoyable activities": "ઉત્સવો અને આનંદદાયક પ્રવૃત્તિઓ માટે અનુકૂળ",
"Powerful but unstable; good for forceful actions": "શક્તિશાળી પણ અસ્થિર; બળવાન કર્મો માટે સારું",
"Highly auspicious for all important undertakings": "બધા મહત્વપૂર્ણ કાર્યો માટે અત્યંત શુભ",
"Challenging; best for spiritual practices and caution": "પડકારજનક; આધ્યાત્મિક પ્રથાઓ અને સાવધાની માટે શ્રેષ્ઠ",
"Good for bold actions and leadership initiatives": "સાહસિક કર્મો અને નેતૃત્વ પહેલો માટે સારું",
"Difficult; better for routine activities and patience": "કઠિન; નિયમિત પ્રવૃત્તિઓ અને ધૈર્ય માટે બહેતર",
"Excellent for all positive and important undertakings": "બધા સકારાત્મક અને મહત્વપૂર્ણ કાર્યો માટે ઉત્કૃષ્ટ",
"Highly favorable for all significant activities": "બધી મહત્વપૂર્ણ પ્રવૃત્તિઓ માટે અત્યંત અનુકૂળ",
"Good for activities that can be completed quickly": "ઝડપથી પૂર્ણ થઈ શકે તેવી પ્રવૃત્તિઓ માટે સારું",
"Excellent for all auspicious and important activities": "બધી શુભ અને મહત્વપૂર્ણ પ્રવૃત્તિઓ માટે ઉત્કૃષ્ટ",
"Favorable for spirituality and pure intentions": "આધ્યાત્મિકતા અને શુદ્ધ ઇરાદાઓ માટે અનુકૂળ",
"Excellent for creative pursuits and spiritual activities": "સર્જનાત્મક પ્રવૃત્તિઓ અને આધ્યાત્મિક પ્રવૃત્તિઓ માટે ઉત્કૃષ્ટ",
"Good for leadership activities and positions of authority": "નેતૃત્વ પ્રવૃત્તિઓ અને સત્તાના પદો માટે સારું",
"Challenging; best for contemplation and careful planning": "પડકારજનક; ચિંતન અને સાવધ આયોજન માટે શ્રેષ્ઠ",

        # Numbers 0-9
        "0": "૦", "1": "૧", "2": "૨", "3": "૩", "4": "૪", 
        "5": "૫", "6": "૬", "7": "૭", "8": "૮", "9": "૯",
        
        # Time indicators
        "AM": "પૂર્વાહ્ન", "PM": "અપરાહ્ન",
        
        # Days of week (sample)
        "Monday": "સોમવાર", "Tuesday": "મંગળવાર", "Wednesday": "બુધવાર", "Thursday": "ગુરુવાર", "Friday": "શુક્રવાર", "Saturday": "શનિવાર", "Sunday": "રવિવાર",
        
        # Months (sample)
        "January": "જાન્યુઆરી", "February": "ફેબ્રુઆરી", "March": "માર્ચ", "April": "એપ્રિલ", "May": "મે", "June": "જૂન", "July": "જુલાઈ", "August": "ઑગસ્ટ", "September": "સપ્ટેમ્બર", "October": "ઑક્ટોબર", "November": "નવેમ્બર", "December": "ડિસેમ્બર",
        
              # Planets
        "Sun": "સૂર્ય",
        "Moon": "ચંદ્ર",
        "Mars": "મંગળ",
        "Mercury": "બુધ",
        "Jupiter": "ગુરુ",
        "Venus": "શુક્ર",
        "Saturn": "શનિ",
        
        # Choghadiya
        "Amrit": "અમૃત",
        "Shubh": "શુભ",
        "Labh": "લાભ",
        "Char": "ચર",
        "Kaal": "કાળ",
        "Rog": "રોગ",
        "Udveg": "ઉદ્વેગ",
        
        # Nature
        "Good": "શુભ",
        "Bad": "અશુભ",
        "Neutral": "સામાન્ય",
        "Excellent": "ઉત્તમ",
        
        # Nakshatras
        "Ashwini": "અશ્વિની",
        "Bharani": "ભરણી",
        "Krittika": "કૃતિકા",
        "Rohini": "રોહિણી",
        "Mrigashira": "મૃગશિરા",
        "Ardra": "આર્દ્રા",
        "Punarvasu": "પુનર્વસુ",
        "Pushya": "પુષ્ય",
        "Ashlesha": "અશ્લેષા",
        "Magha": "મઘા",
        "Purva Phalguni": "પૂર્વ ફાલ્ગુની",
        "Uttara Phalguni": "ઉત્તર ફાલ્ગુની",
        "Hasta": "હસ્તા",
        "Chitra": "ચિત્રા",
        "Swati": "સ્વાતિ",
        "Vishakha": "વિશાખા",
        "Anuradha": "અનુરાધા",
        "Jyeshtha": "જ્યેષ્ઠા",
        "Mula": "મુલા",
        "Purva Ashadha": "પૂર્વ આષાઢા",
        "Uttara Ashadha": "ઉત્તર આષાઢા",
        "Shravana": "શ્રવણ",
        "Dhanishta": "ધનિષ્ઠા",
        "Shatabhisha": "શતભિષજ",
        "Purva Bhadrapada": "પૂર્વ ભાદ્રપદ",
        "Uttara Bhadrapada": "ઉત્તર ભાદ્રપદ",
        "Revati": "રેવતી",
        
        # Nakshatra properties (sample)
        "Ashwini Kumaras": "અશ્વિની કુમાર",
        "Yama (God of Death)": "યમ (મૃત્યુના દેવ)",
        "Agni (Fire God)": "અગ્નિ (આગના દેવ)",
        "Brahma (Creator)": "બ્રહ્મા (સર્જક)",
        "Soma (Moon God)": "સોમ (ચંદ્રના દેવ)",
        "Rudra (Storm God)": "રૂદ્ર (તૂફાનના દેવ)",
        "Aditi (Goddess of Boundlessness)": "આદિતિ (અસીમતાની દેવી)",
        "Brihaspati (Jupiter)": "બૃહસ્પતિ (ગુરુ)",
        "Naga (Serpent Gods)": "નાગ (નાગ દેવતાઓ)",
        "Pitris (Ancestors)": "પિતૃ (પૂર્વજ)",
        "Bhaga (God of Enjoyment)": "ભગ (આનંદના દેવ)",
        "Aryaman (God of Contracts)": "આર્યમન (કોન્ટ્રાક્ટના દેવ)",
        "Savitar (Aspect of Sun)": "સવિતર (સૂર્યનો પાસો)",
        "Vishvakarma (Divine Architect)": "વિશ્વકર્મા (દિવ્ય આર્કિટેક્ટ)",
        "Vayu (Wind God)": "વાયુ (હવા નો દેવ)",
        "Indra-Agni (Gods of Power and Fire)": "ઇન્દ્ર-અગ્નિ (શક્તિ અને આગના દેવો)",
        "Mitra (God of Friendship)": "મિત્ર (મિત્રતાના દેવ)",
        "Indra (King of Gods)": "ઇન્દ્ર (દેવોના રાજા)",
        "Nirriti (Goddess of Destruction)": "નિરૃતિ (વિનાશની દેવી)",
        "Apas (Water Goddesses)": "અપસ (પાણીની દેવીઓ)",
        "Vishvedevas (Universal Gods)": "વિશ્વેદેવ (સર્વવ્યાપી દેવો)",
        "Vishnu": "વિષ્ણુ",
        "Vasus (Gods of Abundance)": "વાસુ (સમૃદ્ધિના દેવો)",
        "Varuna (God of Cosmic Waters)": "વરુણ (કોશિક પાણીના દેવ)",
        "Aja Ekapada (One-footed Goat)": "અજ એકપાદ (એક પગવાળો બકરો)",
        "Ahirbudhnya (Serpent of the Depths)": "અહિરબુધ્ન્ય (ગહનનો નાગ)",
        "Pushan (Nourishing God)": "પુષણ (પોષણના દેવ)",


        #NAKSHTRA QUALITIES in gujarati
        "Energy, activity, enthusiasm, courage, healing abilities, and competitive spirit.": "ઊર્જા, પ્રવૃત્તિ, ઉત્સાહ, ધૈર્ય, ઉપચાર ક્ષમતાઓ, અને સ્પર્ધાત્મક આત્મા.",
        "Discipline, restraint, assertiveness, transformation, and creative potential.": "શિસ્ત, રોકાણ, દૃઢતા, રૂપાંતરણ, અને સર્જનાત્મક સંભાવના.",
        "Purification, clarity, transformation, ambition, and leadership.": "શોધન, સ્પષ્ટતા, રૂપાંતરણ, મહત્તા, અને નેતૃત્વ.",
        "Growth, fertility, prosperity, sensuality, and creativity.": "વિકાસ, પ્રજનન, સમૃદ્ધિ, સંવેદનશીલતા, અને સર્જનાત્મકતા.",
        "Gentleness, curiosity, searching nature, adaptability, and communication skills.": "મૃદુતા, જિજ્ઞાસા, શોધી રહેનાર સ્વભાવ, અનુકૂળતા, અને સંવાદ ક્ષમતાઓ.",
        "Transformation through challenge, intensity, passion, and regenerative power.": "ચેલેન્જ, તીવ્રતા, ઉત્સાહ, અને પુનર્જનન શક્તિ દ્વારા રૂપાંતરણ.",
        "Renewal, optimism, wisdom, generosity, and expansiveness.": "નવજીવન, આશાવાદ, જ્ઞાન, ઉદારતા, અને વિસ્તરણ.",
        "Nourishment, prosperity, spiritual growth, nurturing, and stability.": "પોષણ, સમૃદ્ધિ, આધ્યાત્મિક વિકાસ, સંભાળ, અને સ્થિરતા.",
        "Intuition, mystical knowledge, healing abilities, intensity, and transformative power.": "અનુભૂતિ, રહસ્યમય જ્ઞાન, ઉપચાર ક્ષમતાઓ, તીવ્રતા, અને રૂપાંતરણ શક્તિ.",
        "Leadership, power, ancestry, dignity, and social responsibility.": "નેતૃત્વ, શક્તિ, પૂર્વજ, ગૌરવ, અને સામાજિક જવાબદારી.",
        "Creativity, enjoyment, romance, social grace, and playfulness.": "સર્જનાત્મકતા, આનંદ, રોમાન્સ, સામાજિક કૃપા, અને રમૂજ.",
        "Balance, harmony, partnership, social contracts, and graceful power.": "સંતુલન, સુમેળ, ભાગીદારી, સામાજિક કરાર, અને ગ્રેસફુલ પાવર.",
        "Skill, dexterity, healing abilities, practical intelligence, and manifestation.": "કૌશલ્ય, ચતુરાઈ, ઉપચાર ક્ષમતાઓ, વ્યાવસાયિક બુદ્ધિ, અને પ્રગટતા.",
        "Creativity, design skills, beauty, brilliance, and multi-faceted talents.": "સર્જનાત્મકતા, ડિઝાઇન કૌશલ્ય, સૌંદર્ય, તેજસ્વિતા, અને બહુપહેલુ પ્રતિભા.",
        "Independence, adaptability, movement, self-sufficiency, and scattered brilliance.": "સ્વતંત્રતા, અનુકૂળતા, ગતિ, આત્મનિર્ભરતા, અને વિખરાયેલ તેજસ્વિતા.",
        "Determination, focus, goal achievement, leadership, and purposeful effort.": "નિર્ધારણ, ફોકસ, લક્ષ્ય પ્રાપ્તી, નેતૃત્વ, અને ઉદ્દેશ્યપૂર્ણ પ્રયાસ.",
        "Friendship, cooperation, devotion, loyalty, and success through relationships.": "મિત્રતા, સહકાર, ભક્તિ, વફાદારી, અને સંબંધો દ્વારા સફળતા.",
        "Courage, leadership, protective qualities, seniority, and power.": "ધૈર્ય, નેતૃત્વ, રક્ષણાત્મક ગુણ, વરિષ્ઠતા, અને શક્તિ.",
        "Destruction for creation, getting to the root, intensity, and transformative power.": "સર્જન માટે વિનાશ, મૂળ સુધી પહોંચવું, તીવ્રતા, અને રૂપાંતરણ શક્તિ.",
        "Early victory, invigoration, purification, and unquenchable energy.": "પ્રારંભિક વિજય, ઉર્જાવાન, શુદ્ધિકરણ, અને અવિરત ઊર્જા.",
        "Universal principles, later victory, balance of power, and enduring success.": "સર્વવ્યાપી સિદ્ધાંતો, પછીનો વિજય, શક્તિનું સંતુલન, અને ટકાઉ સફળતા.",
        "Learning, wisdom through listening, connectivity, devotion, and fame.": "શિક્ષણ, સાંભળવાથી જ્ઞાન, જોડાણ, ભક્તિ, અને પ્રસિદ્ધિ.",
        "Wealth, abundance, music, rhythm, and generous spirit.": "ધન, સમૃદ્ધિ, સંગીત, તાલ, અને ઉદાર આત્મા.",
        "Healing, scientific mind, independence, mystical abilities, and expansive awareness.": "ઉપચાર, વૈજ્ઞાનિક મન, સ્વતંત્રતા, રહસ્યમય ક્ષમતાઓ, અને વિસ્તૃત જાગૃતિ.",
        "Intensity, fiery wisdom, transformative vision, and spiritual awakening.": "તીવ્રતા, આગની જ્ઞાન, રૂપાંતરણ દ્રષ્ટિ, અને આધ્યાત્મિક જાગૃતિ.",
        "Deep truth, profound wisdom, serpentine power, and regenerative abilities.": "ગહન સત્ય, ઊંડા જ્ઞાન, નાગિન શક્તિ, અને પુનર્જનન ક્ષમતાઓ.",
        "Nourishment, protection during transitions, abundance, and nurturing wisdom.": "પોષણ, પરિવર્તન દરમિયાન રક્ષણ, સમૃદ્ધિ, અને સંભાળતી જ્ઞાન.",



    
        
        # Common terms
        "Sunrise": "સૂર્યોદય", "Sunset": "સૂર્યાસ્ત",
        "Rahu Kaal": "રાહુ કાળ", "Gulika Kaal": "ગુલિકા કાળ",
        "description": "વર્ણન", "nature": "પ્રકૃતિ",

        #TITHI SPECIALS
"Auspicious for rituals, marriage, travel": "શુભ કાર્ય, લગ્ન, યાત્રા માટે",
"Good for housework, learning": "ઘરનાં કામ, અભ્યાસ માટે સારું",
"Celebrated as Gauri Tritiya (Teej)": "ગૌરી તૃતીયા (તીજ) તરીકે મનાવવામાં આવે છે",
"Sankashti/Ganesh Chaturthi": "સંકષ્ટી/ગણેશ ચતુર્થિ",
"Nag Panchami, Saraswati Puja": "નાગ પંચમી, સરસ્વતી પૂજા",
"Skanda Shashthi, children's health": "સ્કંદ ષષ્ટી, બાળકોના આરોગ્ય માટે",
"Ratha Saptami, start of auspicious work": "રથ સપ્તમી, શુભ કાર્યની શરૂઆત",
"Kala Ashtami, Durga Puja": "કલા અષ્ટમી, દુર્ગા પૂજા",
"Mahanavami, victory over evil": "મહાનવમી, બુરાઈ પર વિજય",
"Vijayadashami/Dussehra": "વિજયા દશમી/દશેરા",
"Fasting day, spiritually uplifting": "ઉપવાસનો દિવસ, આધ્યાત્મિક ઉન્નતિ માટે",
"Breaking Ekadashi fast (Parana)":" એકાદશી ઉપવાસ તોડવો (પરાણ)",
"Pradosh Vrat, Dhanteras": "પ્રદોષ વ્રત, ધનતેરસ",
"Narak Chaturdashi, spiritual cleansing": "નરક ચतुર્દશી, આધ્યાત્મિક શુદ્ધિ માટે",
"Full moon/new moon, ideal for puja, shraddha": "પૂર્ણિમા/અમાવસ્યા, પૂજા, શ્રાદ્ધ માટે આદર્શ",
"Waxing phase of the moon (new to full moon)": "ચાંદની વર્ધમાન અવસ્થા (નવા થી પૂર્ણિમા સુધી)",
"Waning phase (full to new moon)": "ચાંદની ક્ષીણ અવસ્થા (પૂર્ણિમા થી અમાવસ્યા સુધી)",

#Tithi Deity

        "Parvati": "પાર્વતી",
        "Ganesha": "ગણેશ",
        "Skanda": "સ્કંદ",
        "Durga": "દુર્ગા",
        "Lakshmi": "લક્ષ્મી",
        "Saraswati": "સરસ્વતી",
        "Shiva": "શિવ",
        "Vishnu": "વિષ્ણુ",
        "Gauri" : "ગૌરી",
        "Naga Devata": "નાગ દેવતા",
        "Kali, Rudra": "કાળી, રુદ્ર",

      


   # Tithi Names
        "Shukla Pratipada": "શુક્લ પ્રતિપદા",
        "Shukla Dwitiya": "શુક્લ દ્વિતીયા",
        "Shukla Tritiya": "શુક્લ તૃતીયા",
        "Shukla Chaturthi": "શુક્લ ચતુર્થી",
        "Shukla Panchami": "શુક્લ પંચમી",
        "Shukla Shashthi": "શુક્લ ષષ્ઠી",
        "Shukla Saptami": "શુક્લ સપ્તમી",
        "Shukla Ashtami": "શુક્લ અષ્ટમી",
        "Shukla Navami": "શુક્લ નવમી",
        "Shukla Dashami": "શુક્લ દશમી",
        "Shukla Ekadashi": "શુક્લ એકાદશી",
        "Shukla Dwadashi": "શુક્લ દ્વાદશી",
        "Shukla Trayodashi": "શુક્લ ત્રયોદશી",
        "Shukla Chaturdashi": "શુક્લ ચતુર્દશી",
        "Purnima": "પૂર્ણિમા",
        "Krishna Pratipada": "કૃષ્ણ પ્રતિપદા",
        "Krishna Dwitiya": "કૃષ્ણ દ્વિતીયા",
        "Krishna Tritiya": "કૃષ્ણ તૃતીયા",
        "Krishna Chaturthi": "કૃષ્ણ ચતુર્થી",
        "Krishna Panchami": "કૃષ્ણ પંચમી",
        "Krishna Shashthi": "કૃષ્ણ ષષ્ઠી",
        "Krishna Saptami": "કૃષ્ણ સપ્તમી",
        "Krishna Ashtami": "કૃષ્ણ અષ્ટમી",
        "Krishna Navami": "કૃષ્ણ નવમી",
        "Krishna Dashami": "કૃષ્ણ દશમી",
        "Krishna Ekadashi": "કૃષ્ણ એકાદશી",
        "Krishna Dwadashi": "કૃષ્ણ દ્વાદશી",
        "Krishna Trayodashi": "કૃષ્ણ ત્રયોદશી",
        "Krishna Chaturdashi": "કૃષ્ણ ચતુર્દશી",
        "Amavasya": "અમાવસ્યા",

        # Tithi Descriptions
        "Good for starting new ventures and projects. Favorable for planning and organization. Avoid excessive physical exertion and arguments.": "નવા ઉપક્રમો અને પ્રોજેક્ટ્સ શરૂ કરવા માટે સારું. આયોજન અને સંગઠન માટે અનુકૂળ. અતિશય શારીરિક કસરત અને દલીલો ટાળો.",
        "Excellent for intellectual pursuits and learning. Suitable for purchases and agreements. Avoid unnecessary travel and overindulgence.": "બૌદ્ધિક પ્રવૃત્તિઓ અને શિક્ષણ માટે ઉત્કૃષ્ટ. ખરીદી અને કરાર માટે યોગ્ય. બિનજરૂરી મુસાફરી અને અતિશયતા ટાળો.",
        "Auspicious for all undertakings, especially weddings and partnerships. Benefits from charitable activities. Avoid conflicts and hasty decisions.": "બધા કામો માટે શુભ, ખાસ કરીને લગ્ન અને ભાગીદારી. દાનની પ્રવૃત્તિઓમાંથી ફાયદો. સંઘર્ષ અને ઉતાવળના નિર્ણયોથી બચો.",
        "Good for worship of Lord Ganesha and removing obstacles. Favorable for creative endeavors. Avoid starting major projects or signing contracts.": "ભગવાન ગણેશની પૂજા અને અવરોધો દૂર કરવા માટે સારું. સર્જનાત્મક પ્રયાસો માટે અનુકૂળ. મોટા પ્રોજેક્ટ્સ શરૂ કરવા અથવા કોન્ટ્રાક્ટ સાઈન કરવાનું ટાળો.",
        "Excellent for education, arts, and knowledge acquisition. Good for competitions and tests. Avoid unnecessary arguments and rash decisions.": "શિક્ષણ, કળા અને જ્ઞાન પ્રાપ્તિ માટે ઉત્કૃષ્ટ. સ્પર્ધાઓ અને પરીક્ષાઓ માટે સારું. બિનજરૂરી દલીલો અને ઉતાવળના નિર્ણયોથી બચો.",
        "Favorable for victory over enemies and completion of difficult tasks. Good for health initiatives. Avoid procrastination and indecisiveness.": "શત્રુઓ પર વિજય અને કઠિન કામો પૂર્ણ કરવા માટે અનુકૂળ. આરોગ્ય પહેલો માટે સારું. વિલંબ અને અનિર્ણાયકતા ટાળો.",
        "Excellent for health, vitality, and leadership activities. Good for starting treatments. Avoid excessive sun exposure and ego conflicts.": "આરોગ્ય, જીવનશક્તિ અને નેતૃત્વ પ્રવૃત્તિઓ માટે ઉત્કૃષ્ટ. સારવાર શરૂ કરવા માટે સારું. અતિશય સૂર્ય એક્સપોઝર અને અહંકાર સંઘર્ષો ટાળો.",
        "Good for meditation, spiritual practices, and self-transformation. Favorable for fasting. Avoid impulsive decisions and major changes.": "ધ્યાન, આધ્યાત્મિક પ્રથાઓ અને આત્મ-પરિવર્તન માટે સારું. ઉપવાસ માટે અનુકૂળ. આવેગજનક નિર્ણયો અને મોટા ફેરફારો ટાળો.",
        "Powerful for spiritual practices and overcoming challenges. Good for courage and strength. Avoid unnecessary risks and confrontations.": "આધ્યાત્મિક પ્રથાઓ અને પડકારો પર કાબુ પામવા માટે શક્તિશાળી. હિંમત અને બળ માટે સારું. અનાવશ્યક જોખમો અને મુકાબલો ટાળો.",
        "Favorable for righteous actions and religious ceremonies. Good for ethical decisions. Avoid dishonesty and unethical compromises.": "ધાર્મિક કૃત્યો અને ધાર્મિક સમારંભો માટે અનુકૂળ. નૈતિક નિર્ણયો માટે સારું. અસત્યતા અને અનૈતિક સમાધાનો ટાળો.",
        "Highly auspicious for spiritual practices, fasting, and worship of Vishnu. Benefits from restraint and self-control. Avoid overeating and sensual indulgences.": "આધ્યાત્મિક પ્રથાઓ, ઉપવાસ અને વિષ્ણુની પૂજા માટે અત્યંત શુભ. સંયમ અને આત્મ-નિયંત્રણથી લાભ. વધુ ખાવા અને ઇન્દ્રિય સુખોથી બચો.",
        "Good for breaking fasts and charitable activities. Favorable for generosity and giving. Avoid selfishness and stubbornness today.": "ઉપવાસ તોડવા અને દાનની પ્રવૃત્તિઓ માટે સારું. ઉદારતા અને દાન માટે અનુકૂળ. આજે સ્વાર્થ અને હઠથી બચો.",
        "Excellent for beauty treatments, romance, and artistic pursuits. Good for sensual pleasures. Avoid excessive attachment and jealousy.": "સૌંદર્ય સારવાર, પ્રેમ અને કલા માટે ઉત્કૃષ્ટ. ઇન્દ્રિય સુખો માટે સારું. અતિશય લાગણી અને ઈર્ષ્યાથી બચો.",
        "Powerful for worship of Lord Shiva and spiritual growth. Good for finishing tasks. Avoid beginning major projects and hasty conclusions.": "ભગવાન શિવની પૂજા અને આધ્યાત્મિક વિકાસ માટે શક્તિશાળી. કાર્ય પૂર્ણ કરવા માટે સારું. મોટી યોજનાઓ શરૂ કરવા અને ઉતાવળમાં નિષ્કર્ષો કાઢવા ટાળો.",
        "Highly auspicious for spiritual practices, especially related to the moon. Full emotional and mental strength. Avoid emotional instability and overthinking.": "આધ્યાત્મિક પ્રથાઓ માટે અત્યંત શુભ, ખાસ કરીને ચંદ્ર સંબંધિત. સંપૂર્ણ ભાવનાત્મક અને માનસિક શક્તિ. ભાવનાત્મક અસ્થિરતા અને વધુ પડતું વિચારવું ટાળો.",
        "Suitable for planning and reflection. Good for introspection and simple rituals. Avoid major launches or important beginnings.": "યોજન અને ચિંતન માટે યોગ્ય. આત્મનિરીક્ષણ અને સરળ વિધિઓ માટે સારું. મોટા લોન્ચ અથવા મહત્વપૂર્ણ શરૂઆત ટાળો.",
        "Favorable for intellectual pursuits and analytical work. Good for research and study. Avoid impulsive decisions and confrontations.": "બૌદ્ધિક પ્રવૃત્તિઓ અને વિશ્લેષણાત્મક કાર્ય માટે અનુકૂળ. સંશોધન અને અભ્યાસ માટે સારું. આવેગજનક નિર્ણયો અને મુકાબલો ટાળો.",
        "Good for activities requiring courage and determination. Favorable for assertive actions. Avoid aggression and unnecessary force.": "સાહસ અને દૃઢતાની જરૂર પડતી પ્રવૃત્તિઓ માટે સારું. મુખર કાર્ય માટે અનુકૂળ. આક્રમકતા અને અનાવશ્યક બળ ટાળો.",
        "Suitable for removing obstacles and solving problems. Good for analytical thinking. Avoid starting new ventures and major purchases.": "અવરોધો દૂર કરવા અને સમસ્યાઓ હલ કરવા માટે યોગ્ય. વિશ્લેષણાત્મક વિચાર માટે સારું. નવા ઉપક્રમો શરૂ કરવા અને મોટી ખરીદી ટાળો.",
        "Favorable for education, learning new skills, and artistic pursuits. Good for communication. Avoid arguments and misunderstandings.": "શિક્ષણ, નવી કુશળતાઓ શીખવા અને કલાત્મક પ્રવૃત્તિઓ માટે અનુકૂળ. સંવાદ માટે સારું. દલીલો અને ગેરસમજ ટાળો.",
        "Good for competitive activities and overcoming challenges. Favorable for strategic planning. Avoid conflict and excessive competition.": "સ્પર્ધાત્મક પ્રવૃત્તિઓ અને પડકારો પર કાબુ પામવા માટે સારું. વ્યૂહાત્મક આયોજન માટે અનુકૂળ. સંઘર્ષ અને અતિશય સ્પર્ધા ટાળો.",
        "Suitable for health treatments and healing. Good for physical activities and exercise. Avoid overexertion and risky ventures.": "આરોગ્ય સારવાર અને ઉપચાર માટે યોગ્ય. શારીરિક પ્રવૃત્તિઓ અને વ્યાયામ માટે સારું. અતિશય મહેનત અને જોખમી ઉપક્રમો ટાળો.",
        "Powerful for devotional activities, especially to Lord Krishna. Good for fasting and spiritual practices. Avoid excessive materialism and sensual indulgence.": "ભક્તિ પ્રવૃત્તિઓ માટે શક્તિશાળી, ખાસ કરીને ભગવાન કૃષ્ણ માટે. ઉપવાસ અને આધ્યાત્મિક અભ્યાસો માટે સારું. અતિશય ભૌતિકવાદ અને ઇન્દ્રિય સુખો ટાળો.",
        "Favorable for protective measures and strengthening security. Good for courage and determination. Avoid unnecessary risks and fears.": "સુરક્ષાત્મક પગલાં અને સુરક્ષા મજબૂત કરવા માટે અનુકૂળ. હિંમત અને દૃઢતા માટે સારું. અનાવશ્યક જોખમો અને ડર ટાળો.",
        "Good for ethical decisions and righteous actions. Favorable for legal matters. Avoid dishonesty and unethical compromises.": "નૈતિક નિર્ણયો અને ધાર્મિક કૃત્યો માટે સારું. કાનૂની બાબતો માટે અનુકૂળ. અસત્યતા અને અનૈતિક સમાધાન ટાળો.",
        "Highly auspicious for fasting and spiritual practices. Good for detachment and self-control. Avoid overindulgence and material attachment.": "ઉપવાસ અને આધ્યાત્મિક અભ્યાસો માટે અત્યંત શુભ. અનાસક્તિ અને આત્મ-નિયંત્રણ માટે સારું. અતિશયતા અને ભૌતિક લગાવ ટાળો.",
        "Favorable for breaking fasts and charitable activities. Good for generosity and giving. Avoid starting new projects and major decisions.": "ઉપવાસ તોડવા અને દાનની પ્રવૃત્તિઓ માટે અનુકૂળ. ઉદારતા અને દાન માટે સારું. નવા પ્રોજેક્ટ્સ શરૂ કરવા અને મોટા નિર્ણયોથી બચો.",
        "Powerful for spiritual practices, especially those related to transformation. Good for overcoming challenges. Avoid fear and negative thinking.": "આધ્યાત્મિક અભ્યાસો માટે શક્તિશાળી, ખાસ કરીને પરિવર્તન સંબંધિત. પડકારો પર કાબુ પામવા માટે સારું. ડર અને નકારાત્મક વિચારસરણી ટાળો.",
        "Suitable for removing obstacles and ending negative influences. Good for spiritual cleansing. Avoid dark places and negative company.": "અવરોધો દૂર કરવા અને નકારાત્મક અસરો સમાપ્ત કરવા માટે યોગ્ય. આધ્યાત્મિક શુદ્ધીકરણ માટે સારું. અંધારિયા જગ્યાઓ અને નકારાત્મક સંગત ટાળો.",
        "Powerful for ancestral worship and ending karmic cycles. Good for meditation and inner work. Avoid major beginnings and public activities.": "પૂર્વજોની આરાધના અને કર્મ ચક્રો સમાપ્ત કરવા માટે શક્તિશાળી. ધ્યાન અને આંતરિક કામ માટે સારું. મોટી શરૂઆત અને જાહેર પ્રવૃત્તિઓ ટાળો.",

         # Choghadiya meanings
        "Nectar - Most auspicious for all activities": "અમૃત - બધી પ્રવૃત્તિઓ માટે સૌથી શુભ",
        "Auspicious - Good for all positive activities": "શુભ - બધી સકારાત્મક પ્રવૃત્તિઓ માટે સારું",
        "Profit - Excellent for business and financial matters": "લાભ - વ્યવસાય અને નાણાકીય બાબતો માટે ઉત્કૃષ્ટ",
        "Movement - Good for travel and dynamic activities": "ચર - પ્રવાસ અને ગતિશીલ પ્રવૃત્તિઓ માટે સારું",
        "Death - Inauspicious, avoid important activities": "કાળ - અશુભ, મહત્વપૂર્ણ પ્રવૃત્તિઓ ટાળો",
        "Disease - Avoid health-related decisions": "રોગ - આરોગ્ય સંબંધિત નિર્ણયોથી બચો",
        "Anxiety - Mixed results, proceed with caution": "ઉદ્વેગ - મિશ્ર પરિણામો, સાવધાની સાથે આગળ વધો",
        
        # Hora meanings
        "Authority, leadership, government work": "સત્તા, નેતૃત્વ, સરકારી કામ",
        "Emotions, family matters, water-related activities": "લાગણીઓ, કૌટુંબિક બાબતો, પાણી સંબંધિત પ્રવૃત્તિઓ",
        "Energy, sports, real estate, surgery": "ઊર્જા, રમતગમત, સ્થાવર મિલકત, શસ્ત્રક્રિયા",
        "Communication, education, business, travel": "સંચાર, શિક્ષણ, વ્યવસાય, પ્રવાસ",
        "Wisdom, spirituality, teaching, ceremonies": "જ્ઞાન, આધ્યાત્મ, શિક્ષણ, સમારંભ",
        "Arts, beauty, relationships, luxury": "કળા, સુંદરતા, સંબંધો, વૈભવ",
        "Delays, obstacles, hard work, patience required": "વિલંબ, અવરોધો, મહેનત, ધૈર્યની જરૂર",

         # Inauspicious periods
        "Rahu Kaal is considered an inauspicious time for starting important activities.": "રાહુ કાળને મહત્વપૂર્ણ પ્રવૃત્તિઓ શરૂ કરવા માટે અશુભ સમય માનવામાં આવે છે.",
        "Gulika Kaal is considered an unfavorable time period.": "ગુલિકા કાળને પ્રતિકૂળ સમયગાળો માનવામાં આવે છે.",
        "Yamaghanta is considered inauspicious for important activities.": "યમઘંટાને મહત્વપૂર્ણ પ્રવૃત્તિઓ માટે અશુભ માનવામાં આવે છે.",
        
        # Subh Muhurats
        "Brahma Muhurat": "બ્રહ્મ મુહૂર્ત",
        "Sacred early morning hours ideal for spiritual practices.": "આધ્યાત્મિક અભ્યાસો માટે આદર્શ પવિત્ર વહેલી સવારના કલાકો.",
        "Abhijit Muhurat": "અભિજીત મુહૂર્ત",
        "Highly auspicious for starting new ventures.": "નવા ઉપક્રમોની શરૂઆત માટે અત્યંત શુભ.",

        #NAKSHTRA DESCRIPTIONS

       "Ashwini is symbolized by a horse's head and ruled by Ketu. People born under this nakshatra are often quick, energetic, and enthusiastic. They excel in competitive environments, possess natural healing abilities, and have a strong desire for recognition. Ashwini brings qualities of intelligence, charm, and restlessness, making natives good at starting new ventures but sometimes impatient. It's auspicious for medical pursuits, transportation, sports, and quick endeavors.": "અશ્વિની નક્ષત્રનું પ્રતિક ઘોડાનું માથું છે અને તે કેતુ દ્વારા શાસિત છે. આ નક્ષત્રમાં જન્મેલા લોકો ઝડપથી ક્રિયાશીલ, ઉત્સાહી અને ચતુર હોય છે. તેઓ સ્પર્ધાત્મક પરિસ્થિતિઓમાં સારું કરતા હોય છે અને સ્વાભાવિક રીતે ચિકિત્સા ક્ષમતા ધરાવે છે. આ નક્ષત્ર નવી શરૂઆત, આરોગ્ય સેવાઓ, યાત્રા અને રમતગમત માટે શુભ માનવામાં આવે છે.",
        
        "Bharani is ruled by Venus and presided over by Yama, the god of death. This nakshatra represents the cycle of creation, maintenance, and dissolution. Bharani natives are often disciplined, determined, and possess strong creative energies. They excel in transforming circumstances and handling resources. This nakshatra supports activities related to cultivation, growth processes, financial management, and endeavors requiring perseverance and discipline.": "ભરણી નક્ષત્ર शुक्रના અધિન છે અને યમ દેવતા દ્વારા શાસિત છે. આ નક્ષત્ર સર્જન, જાળવણી અને વિનાશના ચક્રનું પ્રતિનિધિત્વ કરે છે. ભરણીમાં જન્મેલા વ્યક્તિઓમાં શિસ્ત, નિર્ધારણ અને સર્જનાત્મક શક્તિઓ હોય છે. આ નક્ષત્ર ખેતી, નાણાકીય વ્યવસ્થાપન અને અનુકૂળ યોજના માટે ઉત્તમ છે.",
        
        "Krittika is ruled by the Sun and associated with Agni, the fire god. People born under this nakshatra often possess sharp intellect, strong ambition, and purifying energy. They can be brilliant, focused, and passionate about their pursuits. Krittika is favorable for activities requiring purification, leadership roles, analytical work, and transformative processes. Its energy supports clarity, precision, and the burning away of obstacles.": "કૃત્તિકા નક્ષત્ર સૂર્ય દ્વારા શાસિત છે અને અગ્નિ દેવ સાથે સંકળાયેલું છે. આ નક્ષત્રના જાતકો તીવ્ર બુદ્ધિશાળી, ઉદ્યોગી અને શક્તિશાળી હોય છે. નેતૃત્વ, વિશ્લેષણાત્મક કાર્ય અને પરિવર્તનાત્મક પ્રવૃત્તિઓ માટે શુભ છે.",
        
        "Rohini is ruled by the Moon and associated with Lord Brahma. This nakshatra represents growth, nourishment, and material abundance. Natives of Rohini are often creative, sensual, and possess natural artistic talents. They value stability, beauty, and comfort. This nakshatra is excellent for activities related to agriculture, artistic pursuits, luxury industries, stable relationships, and endeavors requiring patience and sustained effort.": "રોહિણી નક્ષત્ર ચંદ્ર દ્વારા શાસિત થાય છે અને બ્રહ્મા સાથે સંકળાયેલું છે. આ નક્ષત્ર વૃદ્ધિ, પોષણ અને સામગ્રીની સમૃદ્ધિનું પ્રતિનિધિત્વ કરે છે. રોહિણીના જાતકો સર્જનાત્મક, સંવેદનશીલ અને કુદરતી કલા પ્રતિભા ધરાવતા હોય છે. તેઓ સ્થિરતા, સૌંદર્ય અને આરામને મહત્વ આપે છે. આ નક્ષત્ર કૃષિ, કલા, વૈભવ ઉદ્યોગો, સ્થિર સંબંધો અને ધીરજ અને સતત પ્રયાસોની જરૂર પડતી પ્રવૃત્તિઓ માટે ઉત્તમ છે.",
        
        "Mrigashira is ruled by Mars and presided over by Soma. Symbolized by a deer's head, it represents the searching, gentle qualities of exploration and discovery. People born under this nakshatra are often curious, adaptable, and possess excellent communication skills. They have a natural ability to seek out knowledge and opportunities. Mrigashira supports research, exploration, communication-based ventures, travel, and pursuits requiring both gentleness and persistence.": "મૃગશિરા નક્ષત્ર મંગળ દ્વારા શાસિત છે અને સોમ દેવ સાથે જોડાયેલું છે. આ નક્ષત્ર શોધી કાઢવાની ક્ષમતા, સરળતા અને સંવાદ માટે યોગ્ય છે. જાતકો જિજ્ઞાસુક અને તર્કસંગત હોય છે.",
        
        "Ardra is ruled by Rahu and associated with Rudra, the storm god. This powerful nakshatra represents transformation through intensity and challenge. Ardra natives often possess strong emotional depth, persistence through difficulties, and regenerative capabilities. They can be passionate, determined, and unafraid of life's storms. This nakshatra supports endeavors requiring breaking through obstacles, profound change, crisis management, and transformative healing.": "આરદ્રા નક્ષત્ર રાહુ દ્વારા શાસિત થાય છે અને રુદ્ર દેવતા સાથે સંકળાયેલું છે. આ નક્ષત્ર પરિવર્તનશીલતા, ઊંડા લાગણીઓ અને સંઘર્ષમાંથી ઊભા થવાની ક્ષમતા દર્શાવે છે. આરદ્રાના જાતકો લાગણીશીલ, જિજ્ઞાસુ અને જીવનના તૂફાનો સામનો કરવા માટે નિર્ભય હોય છે.",
        
        "Punarvasu is ruled by Jupiter and presided over by Aditi, goddess of boundlessness. This nakshatra represents renewal, return to wealth, and expansive growth. People born under Punarvasu often possess natural wisdom, generosity, and optimistic outlook. They excel at bringing renewal to situations and seeing the broader perspective. This nakshatra supports education, spiritual pursuits, teaching, counseling, and ventures requiring wisdom, renewal, and positive growth.": "પુનર્વસુ નક્ષત્ર બૃહસ્પતિ દ્વારા શાસિત છે અને અદિતિ સાથે સંકળાયેલું છે. આ નક્ષત્ર પુનઃપ્રાપ્તિ, આશાવાદ અને આધ્યાત્મિક જ્ઞાનનું પ્રતિક છે. પુનર્વસુમાં જન્મેલા લોકો સામાન્ય રીતે જ્ઞાનશીલ, ઉદાર અને આશાવાદી હોય છે.",
        
        "Pushya is ruled by Saturn and associated with Brihaspati. Considered one of the most auspicious nakshatras, it represents nourishment, prosperity, and spiritual abundance. Pushya natives are often nurturing, responsible, and possess strong moral values. They excel at creating stability and growth. This nakshatra is excellent for beginning important ventures, spiritual practices, charitable work, healing professions, and endeavors requiring integrity, nourishment, and sustained positive growth.": "પૂષ્ય નક્ષત્ર શનિ દ્વારા શાસિત છે અને બૃહસ્પતિ સાથે સંકળાયેલું છે. આ નક્ષત્ર સૌથી શુભ માનવામાં આવે છે અને પોષણ, સમૃદ્ધિ અને આધ્યાત્મિક ઉન્નતિનું પ્રતિનિધિત્વ કરે છે. પુષ્યના જાતકો સામાન્ય રીતે પોષણશીલ, જવાબદાર અને મજબૂત નૈતિક મૂલ્યો ધરાવતા હોય છે.",
        
        "Ashlesha is ruled by Mercury and presided over by the Nagas. Symbolized by a coiled serpent, it represents kundalini energy, mystical knowledge, and penetrating insight. People born under this nakshatra often possess strong intuition, healing abilities, and magnetic personality. They have natural investigative skills and understand hidden matters. Ashlesha supports medical research, psychological work, occult studies, and endeavors requiring penetrating intelligence and transformative power.": "આશ્લેષા નક્ષત્ર બુધ દ્વારા શાસિત છે અને નાગ દેવતાઓ સાથે સંકળાયેલું છે. આ નક્ષત્ર રહસ્યવાદ, તીવ્ર બુદ્ધિ અને આંતરિક શક્તિનું પ્રતિક છે. જાતકો ચતુર, દૂરસંચારી અને મનગમતા પ્રશ્નો ઉકેલવા સક્ષમ હોય છે.",
        
        "Magha is ruled by Ketu and associated with the Pitris, or ancestral spirits. This nakshatra represents power, leadership, and ancestral connections. Magha natives often possess natural authority, dignity, and a sense of duty to their lineage. They value honor and recognition. This nakshatra supports leadership roles, governmental work, ancestral healing, ceremonial activities, and ventures requiring public recognition, authority, and connection to tradition and heritage.": "મઘા નક્ષત્ર કેતુ દ્વારા શાસિત છે અને પિતૃઓ સાથે સંકળાયેલું છે. આ નક્ષત્ર માન-સન્માન, પરંપરા અને સામાજિક સ્થાનનું પ્રતિનિધિત્વ કરે છે. જાતકો ગૌરવપૂર્ણ, પ્રતિષ્ઠિત અને નેતૃત્વ ક્ષમતા ધરાવનારા હોય છે.",
        
        "Purva Phalguni is ruled by Venus and presided over by Bhaga, god of enjoyment. This nakshatra represents creative expression, pleasure, and social harmony. People born under this nakshatra often possess charm, creativity, and natural social skills. They enjoy beauty and relationships. Purva Phalguni supports artistic endeavors, romance, entertainment, social activities, and ventures requiring creativity, pleasure, and harmonious social connections.": "પૂર્વ ફાલ્ગુની નક્ષત્ર શુક્ર દ્વારા શાસિત છે અને ભૂમિ સાથે સંકળાયેલું છે. આ નક્ષત્ર પ્રેમ, યોનિ અને રચનાત્મકતાનું પ્રતિક છે. જાતકો આકર્ષક, પ્રેમાળ અને સામાજિક હોય છે.",
        
        "Uttara Phalguni is ruled by the Sun and presided over by Aryaman, god of contracts and patronage. This nakshatra represents harmonious social relationships, beneficial agreements, and balanced partnerships. Natives of this nakshatra often value fairness, social harmony, and mutually beneficial relationships. They possess natural diplomatic abilities. This nakshatra supports marriage, contracts, partnerships, social networking, and endeavors requiring balance, integrity, and harmonious cooperation.": "ઉત્તર ફાલ્ગુની નક્ષત્ર સૂર્ય દ્વારા શાસિત છે અને આર્યમાન સાથે સંકળાયેલું છે. આ નક્ષત્ર સામાજિકતા, સહયોગ અને રચનાત્મકતાનું પ્રતિક છે. જાતકો સહાનુભૂતિશીલ, સહયોગી અને રચનાત્મક હોય છે. આ નક્ષત્ર સામાજિક કાર્યોથી લઈને કલા અને રચનાત્મક પ્રોજેક્ટ્સ માટે શુભ છે.",
        
        "Hasta is ruled by the Moon and presided over by Savitar. Symbolized by a hand, this nakshatra represents practical skills, craftsmanship, and manifesting ability. People born under Hasta often possess excellent manual dexterity, practical intelligence, and healing abilities. They excel at bringing ideas into form. This nakshatra supports craftsmanship, healing work, practical skills development, technological endeavors, and activities requiring precision, skill, and the ability to manifest ideas into reality.": "હસ્તા નક્ષત્ર ચંદ્ર દ્વારા શાસિત છે અને વિશ્વકર્મા સાથે સંકળાયેલું છે. આ નક્ષત્ર કૌશલ્ય, કાર્યકુશળતા અને સેવા માટે ઉત્તમ માનવામાં આવે છે. જાતકો કૌશલ્યવાન, સર્જનાત્મક અને વ્યવસાયિક હોય છે.",
        
        "Chitra is ruled by Mars and associated with Vishvakarma, the divine architect. This nakshatra represents creative design, multi-faceted brilliance, and artistic excellence. Chitra natives often possess diverse talents, creative vision, and appreciation for beauty and design. They tend to stand out in whatever they do. This nakshatra supports design work, architecture, fashion, arts, strategic planning, and endeavors requiring creative brilliance, versatility, and visual excellence.": "ચિત્રા નક્ષત્ર મંગળ દ્વારા શાસિત છે અને વિશ્વકર્મા સાથે સંકળાયેલું છે. આ નક્ષત્ર સર્જનાત્મકતા, સૌંદર્ય અને કલા માટે ઉત્તમ માનવામાં આવે છે. જાતકો કલાત્મક, વૈભવી અને સર્જનાત્મક હોય છે.",
        
        "Swati is ruled by Rahu and presided over by Vayu, god of wind. This nakshatra represents independent movement, self-sufficiency, and scattered brilliance. People born under Swati often possess adaptability, independent thinking, and movement-oriented talents. They value freedom and have an unpredictable quality. This nakshatra supports independent ventures, travel, aviation, communication, and endeavors requiring adaptability, independence, and the ability to spread ideas widely.": "સ્વાતિ નક્ષત્ર રાહુ દ્વારા શાસિત છે અને વાયુ દેવતા સાથે સંકળાયેલું છે. આ નક્ષત્ર સ્વતંત્રતા, અનુકૂળતા અને પરિવર્તનશીલતાનું પ્રતિક છે. જાતકો સ્વતંત્ર, અનુકૂળ અને આધ્યાત્મિક હોય છે.",
        
        "Vishakha is ruled by Jupiter and associated with Indra-Agni. This nakshatra represents focused determination, purposeful effort, and achievement of goals. Vishakha natives are often ambitious, determined, and possess leadership qualities combined with spiritual focus. They excel at achieving objectives through sustained effort. This nakshatra supports goal-setting, leadership roles, competitive activities, spiritual pursuits with practical aims, and endeavors requiring determination, focus, and strategic achievement.": "વિશાખા નક્ષત્ર જુપિટર દ્વારા શાસિત છે અને જૈમિની સાથે સંકળાયેલું છે. આ નક્ષત્ર પ્રગતિ, સમૃદ્ધિ અને જ્ઞાનનું પ્રતિક છે. જાતકો પ્રગતિશીલ, જ્ઞાની અને સામાજિક હોય છે.",
        
        "Anuradha is ruled by Saturn and presided over by Mitra, god of friendship. This nakshatra represents successful cooperation, friendship, and devotion. People born under Anuradha often possess natural diplomatic skills, loyalty, and ability to succeed through harmonious relationships. They value friendship and cooperation. This nakshatra supports teamwork, diplomatic endeavors, friendship-based ventures, devotional practices, and activities requiring cooperation, loyalty, and mutual success.": "અનુરાધા નક્ષત્ર શનિ દ્વારા શાસિત છે અને નાગ દેવતાઓ સાથે સંકળાયેલું છે. આ નક્ષત્ર સામાજિકતા, મિત્રતા અને સહકારનું પ્રતિક છે. જાતકો સહાનુભૂતિશીલ, સહયોગી અને સમર્પિત હોય છે.",
        
        "Jyeshtha is ruled by Mercury and associated with Indra, king of the gods. This nakshatra represents seniority, protective leadership, and courage. Jyeshtha natives often possess natural leadership abilities, protective instincts, and desire for recognition. They have strong personalities and sense of authority. This nakshatra supports leadership roles, protective services, senior positions, mentorship, and endeavors requiring courage, protection of others, and the wielding of authority with intelligence.": "જ્યેષ્ઠા નક્ષત્ર મંગળ દ્વારા શાસિત છે અને ઇન્દ્ર સાથે સંકળાયેલું છે. આ નક્ષત્ર સામાજિકતા, નેતૃત્વ અને શક્તિનું પ્રતિક છે. જાતકો શક્તિશાળી, પ્રતિષ્ઠિત અને નેતૃત્વ ક્ષમતા ધરાવનારા હોય છે.",
        
        "Mula is ruled by Ketu and presided over by Nirriti. Its name means 'root' and it represents the destructive power that precedes creation. People born under Mula often possess investigative abilities, interest in fundamental principles, and transformative energy. They can get to the root of matters. This nakshatra supports research, elimination of obstacles, fundamental change, spiritual pursuits, and endeavors requiring deep investigation, uprooting of problems, and complete transformation.": "મુલા નક્ષત્ર કેતુ દ્વારા શાસિત છે અને નાગ દેવતાઓ સાથે સંકળાયેલું છે. આ નક્ષત્ર ગૂઢ જ્ઞાન, આધ્યાત્મિકતા અને પરિવર્તનનું પ્રતિક છે. જાતકો આધ્યાત્મિક, ગૂઢ જ્ઞાન ધરાવનારા અને પરિવર્તનશીલ હોય છે.",
        
        "Purva Ashadha is ruled by Venus and associated with Apas, the water goddesses. This nakshatra represents early victory, invigoration, and unquenchable energy. Purva Ashadha natives often possess determination, enthusiasm, and ability to overcome obstacles through sustained effort. They have purifying energy and natural leadership. This nakshatra supports initial phases of important projects, leadership roles, water-related activities, and endeavors requiring determination, purification, and invincible enthusiasm.": "પૂર્વ આષાઢા નક્ષત્ર વેનસ દ્વારા શાસિત છે અને વૈષ્ણવી સાથે સંકળાયેલું છે. આ નક્ષત્ર પ્રેમ, સૌંદર્ય અને સામાજિક જીવનનું પ્રતિક છે. જાતકો આકર્ષક, પ્રેમાળ અને સામાજિક હોય છે.",
        
        "Uttara Ashadha is ruled by the Sun and presided over by the Vishvedevas. This nakshatra represents later victory, universal principles, and balanced power. People born under this nakshatra often possess strong principles, balanced leadership abilities, and capacity for enduring success. They value universal truths and lasting achievement. This nakshatra supports long-term projects, ethical leadership, philosophical pursuits, and endeavors requiring principled action, balanced power, and sustained, honorable success.": "ઉત્તર આષાઢા નક્ષત્ર સૂર્ય દ્વારા શાસિત છે અને અદિતિ સાથે સંકળાયેલું છે. આ નક્ષત્ર શક્તિ, ઉર્જા અને આત્મવિશ્વાસનું પ્રતિક છે. જાતકો શક્તિશાળી, આત્મવિશ્વાસી અને નેતૃત્વ ક્ષમતા ધરાવનારા હોય છે.",
        
        "Shravana is ruled by the Moon and associated with Lord Vishnu. Its name relates to hearing and it represents learning through listening, connectivity, and devotion. Shravana natives often possess excellent listening skills, learning abilities, and connective intelligence. They value wisdom and harmonious relationships. This nakshatra supports education, communication, devotional practices, networking, and endeavors requiring good listening, wisdom gathering, connectivity, and the harmonizing of diverse elements.": "શ્રવણ નક્ષત્ર બુધ દ્વારા શાસિત છે અને વિશ્વકર્મા સાથે સંકળાયેલું છે. આ નક્ષત્ર સંવાદ, સાંભળવા અને સમજવા ક્ષમતા માટે ઉત્તમ માનવામાં આવે છે. જાતકો સંવાદી, સમજદાર અને શિક્ષણમાં રસ ધરાવનારા હોય છે.",
        
        "Dhanishta is ruled by Mars and presided over by the Vasus. This nakshatra represents wealth, rhythm, music, and generous abundance. People born under Dhanishta often possess musical talents, rhythmic abilities, and natural generosity. They have a prosperous energy and ability to create wealth. This nakshatra supports musical endeavors, wealth creation, philanthropic activities, and ventures requiring rhythm, momentum, prosperous energy, and the generous sharing of abundance.": "દનિષ્ઠા નક્ષત્ર રાહુ દ્વારા શાસિત છે અને નાગ દેવતાઓ સાથે સંકળાયેલું છે. આ નક્ષત્ર સામાજિકતા, સંગીત અને કલા માટે ઉત્તમ માનવામાં આવે છે. જાતકો સામાજિક, સંગીતપ્રેમી અને કલાત્મક હોય છે.",
        
        "Shatabhisha is ruled by Rahu and associated with Varuna. Its name means 'hundred healers' and it represents healing powers, scientific understanding, and cosmic awareness. Shatabhisha natives often possess innovative thinking, healing abilities, and independent perspective. They can perceive beyond conventional boundaries. This nakshatra supports medical practices, scientific research, alternative healing, mystical pursuits, and endeavors requiring innovation, independence of thought, and broad awareness of interconnected systems.": "શતભિષજ નક્ષત્ર શનિ દ્વારા શાસિત છે અને વાયુ સાથે સંકળાયેલું છે. આ નક્ષત્ર આધ્યાત્મિકતા, સ્વતંત્રતા અને પરિવર્તનનું પ્રતિક છે. જાતકો આધ્યાત્મિક, સ્વતંત્ર અને પરિવર્તનશીલ હોય છે.",
        
        "Purva Bhadrapada is ruled by Jupiter and presided over by Aja Ekapada. This nakshatra represents fiery wisdom, intensity, and spiritual awakening through challenge. People born under this nakshatra often possess penetrating insight, transformative vision, and ability to inspire others. They can be intensely focused on their path. This nakshatra supports spiritual pursuits, inspirational leadership, transformative teaching, and endeavors requiring intensity, deep wisdom, and the courage to walk a unique spiritual path.": "પૂર્વ ભાદ્રપદ નક્ષત્ર જુપિટર દ્વારા શાસિત છે અને અશ્વિની કુમારો સાથે સંકળાયેલું છે. આ નક્ષત્ર પ્રેમ, સૌંદર્ય અને સામાજિક જીવનનું પ્રતિક છે. જાતકો આકર્ષક, પ્રેમાળ અને સામાજિક હોય છે.",
        
        "Uttara Bhadrapada is ruled by Saturn and associated with Ahirbudhnya. This nakshatra represents deep truth, serpentine wisdom, and regenerative power from the depths. Uttara Bhadrapada natives often possess profound understanding, regenerative abilities, and capacity to bring hidden truths to light. They value depth and authenticity. This nakshatra supports deep research, psychological work, spiritual transformation, and endeavors requiring profound wisdom, regenerative power, and the ability to work with hidden forces.": "ઉત્તર ભાદ્રપદ નક્ષત્ર શુક્ર દ્વારા શાસિત છે અને અશ્વિની કુમારો સાથે સંકળાયેલું છે. આ નક્ષત્ર શક્તિ, ઉર્જા અને આત્મવિશ્વાસનું પ્રતિક છે. જાતકો શક્તિશાળી, આત્મવિશ્વાસી અને નેતૃત્વ ક્ષમતા ધરાવનારા હોય છે.",
        
        "Revati is ruled by Mercury and presided over by Pushan. As the final nakshatra, it represents completion, nourishment, and protection during transitions. People born under Revati often possess nurturing qualities, protective wisdom, and ability to nourish others across transitions. They tend to be caring and supportive. This nakshatra supports completion of cycles, nurturing activities, transitional guidance, and endeavors requiring gentle wisdom, nourishing qualities, and the ability to help others move smoothly through life's transitions.": "રેવતી નક્ષત્ર બુધ દ્વારા શાસિત છે અને પુષ્પા સાથે સંકળાયેલું છે. આ નક્ષત્ર સંવાદ, સાંભળવા અને સમજવા ક્ષમતા માટે ઉત્તમ માનવામાં આવે છે. જાતકો સંવાદી, સમજદાર અને શિક્ષણમાં રસ ધરાવનારા હોય છે.",

        #NAKSHTRA QUALITIES
        "Gentleness, curiosity, searching nature, adaptability, and communication skills.":"નમ્રતા, જિજ્ઞાસા, શોધી રહેવુ, અનુકૂળતા અને સંવાદ ક્ષમતા.",

        "Energy, activity, enthusiasm, courage, healing abilities, and competitive spirit.":"ઊર્જા, પ્રવૃત્તિ, ઉત્સાહ, ધૈર્ય, ઉપચાર ક્ષમતા, અને સ્પર્ધાત્મક આત્મા.",

        "Discipline, restraint, assertiveness, transformation, and creative potential.": "અનુશાસન, રોકાણ, દૃઢતા, પરિવર્તન, અને સર્જનાત્મક સંભાવના.",

        "Purification, clarity, transformation, ambition, and leadership.":"શોધન, સ્પષ્ટતા, પરિવર્તન, મહત્તા, અને નેતૃત્વ.",

        "Growth, fertility, prosperity, sensuality, and creativity.":"વિકાસ, પ્રજનન, સમૃદ્ધિ, સંવેદનશીલતા, અને સર્જનાત્મકતા.",

        "Transformation through challenge, intensity, passion, and regenerative power.":"ચેલેન્જ, તીવ્રતા, ઉત્સાહ, અને પુનર્જીવિત શક્તિ દ્વારા પરિવર્તન.",

        "Renewal, optimism, wisdom, generosity, and expansiveness.":"નવજીવન, આશાવાદ, જ્ઞાન, ઉદારતા, અને વિસ્તરણ.",

        "Nourishment, prosperity, spiritual growth, nurturing, and stability.":"પોષણ, સમૃદ્ધિ, આધ્યાત્મિક વિકાસ, સંભાળ, અને સ્થિરતા.",

        "Intuition, mystical knowledge, healing abilities, intensity, and transformative power.":"અનુભૂતિ, રહસ્યમય જ્ઞાન, ઉપચાર ક્ષમતા, તીવ્રતા, અને પરિવર્તનશીલ શક્તિ.",

        "Leadership, power, ancestry, dignity, and social responsibility.":"નેતૃત્વ, શક્તિ, વંશજ, ગૌરવ, અને સામાજિક જવાબદારી.",

        "Creativity, enjoyment, romance, social grace, and playfulness.":"સર્જનાત્મકતા, આનંદ, પ્રેમ, સામાજિક ગ્રેસ, અને રમૂજભર્યું સ્વભાવ.",

        "Balance, harmony, partnership, social contracts, and graceful power.":"સંતુલન, સુમેળ, ભાગીદારી, સામાજિક કરાર, અને ગ્રેસફુલ પાવર.",

        "Skill, dexterity, healing abilities, practical intelligence, and manifestation.":"કૌશલ્ય, ચતુરાઈ, ઉપચાર ક્ષમતા, વ્યાવસાયિક બુદ્ધિ, અને પ્રગટતા.",

        "Creativity, design skills, beauty, brilliance, and multi-faceted talents.":"સર્જનાત્મકતા, ડિઝાઇન કૌશલ્ય, સૌંદર્ય, તેજસ્વિતા, અને બહુ-પહેલુ પ્રતિભા.",

        "Independence, adaptability, movement, self-sufficiency, and scattered brilliance.":"સ્વતંત્રતા, અનુકૂળતા, ગતિ, આત્મનિર્ભરતા, અને વિખરાયેલ તેજસ્વિતા.",

        "Determination, focus, goal achievement, leadership, and purposeful effort.":"નિર્ધારણ, ફોકસ, લક્ષ્ય પ્રાપ્તી, નેતૃત્વ, અને ઉદ્દેશપૂર્વકનો પ્રયાસ.",

        "Friendship, cooperation, devotion, loyalty, and success through relationships.":"મિત્રતા, સહકાર, ભક્તિ, વફાદારી, અને સંબંધો દ્વારા સફળતા.",

        "Courage, leadership, protective qualities, seniority, and power.":"ધૈર્ય, નેતૃત્વ, રક્ષણાત્મક ગુણ, વરિષ્ઠતા, અને શક્તિ.",

        "Destruction for creation, getting to the root, intensity, and transformative power.":"સર્જન માટે વિનાશ, મૂળ સુધી પહોંચવું, તીવ્રતા, અને પરિવર્તનશીલ શક્તિ.",

        "Early victory, invigoration, purification, and unquenchable energy.":"પ્રારંભિક વિજય, ઉર્જાવાન, શુદ્ધિકરણ, અને અવિરત ઊર્જા.",

        "Universal principles, later victory, balance of power, and enduring success.":"સર્વવ્યાપી સિદ્ધાંતો, પછીનો વિજય, શક્તિનું સંતુલન, અને ટકાઉ સફળતા.",

        "Learning, wisdom through listening, connectivity, devotion, and fame.":"શિક્ષણ, સાંભળવાથી જ્ઞાન, જોડાણ, ભક્તિ, અને પ્રસિદ્ધિ.",

        "Wealth, abundance, music, rhythm, and generous spirit.":"ધન, સમૃદ્ધિ, સંગીત, તાલ, અને ઉદાર આત્મા.",

        "Healing, scientific mind, independence, mystical abilities, and expansive awareness.":"ઉપચાર, વૈજ્ઞાનિક મન, સ્વતંત્રતા, રહસ્યમય ક્ષમતા, અને વિસ્તૃત જાગૃતિ.",

        "Intensity, fiery wisdom, transformative vision, and spiritual awakening.":"તીવ્રતા, આગેવાનીનો જ્ઞાન, પરિવર્તનશીલ દ્રષ્ટિ, અને આધ્યાત્મિક જાગૃતિ.",

        "Deep truth, profound wisdom, serpentine power, and regenerative abilities.":"ગહન સત્ય, ઊંડા જ્ઞાન, નાગિન શક્તિ, અને પુનર્જીવિત ક્ષમતા.",

        "Nourishment, protection during transitions, abundance, and nurturing wisdom.":"પોષણ, સંક્રમણ દરમિયાન રક્ષણ, સમૃદ્ધિ, અને સંભાળવાળું જ્ઞાન.",

        "Vishkambha": "વિશ્કંભ",
        "Priti": "પ્રિતિ",
        "Ayushman": "આયુષ્માન",
        "Saubhagya": "સૌભાગ્ય",
        "Shobhana": "શોભના",
        "Atiganda": "અતિગંડ",
        "Sukarman": "સુકર્મણ",
        "Dhriti": "ધૃતિ",
        "Shula": "શૂળ",
        "Ganda": "ગંડ",
        "Vriddhi": "વૃદ્ધિ",
        "Dhruva": "ધ્રુવા",
        "Vyaghata": "વ્યાઘાત",
        "Harshana": "હર્ષણ",
        "Vajra": "વજ્ર",
        "Siddhi": "સિદ્ધિ",
        "Vyatipata": "વ્યતિપાત",
        "Variyana": "વારીયાણા",
        "Parigha": "પરિઘ",
        "Shiva": "શિવ",
        "Siddha": "સિદ્ધ",
        "Sadhya": "સાધ્ય",
        "Shubha": "શુભ",
        "Shukla": "શુક્લ",
        "Brahma": "બ્રહ્મ",
        "Indra": "ઇન્દ્ર",
        "Vaidhriti": "વૈધૃતી"

    }
}

def translate_numbers_to_script(text: str, target_language: str) -> str:
    """Convert Arabic numerals to Hindi/Gujarati numerals"""
    if target_language.lower() not in ["hindi", "gujarati"]:
        return text
    
    translations = PANCHANG_TRANSLATIONS.get(target_language.lower(), {})
    
    # Replace each digit
    for arabic, script in translations.items():
        if arabic.isdigit():
            text = text.replace(arabic, script)
    
    return text

def translate_panchang_text(text: str, target_language: str) -> str:
    """Manual translation for Panchang-specific text"""
    if target_language.lower() == "english":
        return text
    
    if target_language.lower() not in ["hindi", "gujarati"]:
        return text
    
    translations = PANCHANG_TRANSLATIONS.get(target_language.lower(), {})
    
    # First translate the text content
    translated_text = translations.get(text, text)
    
    # Then translate any numbers in the text
    translated_text = translate_numbers_to_script(translated_text, target_language)
    
    return translated_text

@app.post("/nakshatra")
async def nakshatra_endpoint(request: NakshatraRequest):
    """API endpoint to get Nakshatra information"""
    try:
        # Extract parameters from request
        date_str = request.date
        time_str = request.time
        latitude = request.latitude
        longitude = request.longitude
        timezone_str = request.timezone
        language = request.language
        
        logger.info(f"Nakshatra request: date={date_str}, time={time_str}, lat={latitude}, lon={longitude}, language={language}")
        
        # Validate language
        valid_languages = ["English", "Hindi", "Gujarati"]
        if language not in valid_languages:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid language. Please provide one of: {', '.join(valid_languages)}"
            )
        
        # Parse date and time
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            time_parts = time_str.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            # Create datetime object
            target_datetime = datetime.combine(
                target_date, 
                datetime.min.time().replace(hour=hour, minute=minute)
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date or time format. Use YYYY-MM-DD for date and HH:MM for time"
            )
        
        # Get nakshatra information asynchronously
        result = await asyncio.to_thread(
            get_nakshatra_info,
            target_datetime,
            latitude,
            longitude,
            timezone_str
        )
        
        # Add language support to the result
        if language != "English" and result:
            # Apply translations if needed
            result["language"] = language
            # You can add specific translation logic here if needed
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing your request: {str(e)}"
        )

def get_nakshatra_info(date: datetime, latitude: float, longitude: float, timezone_str: str = "Asia/Kolkata") -> Dict:
    """
    Calculate Nakshatra for a given date and location using accurate
    astronomical calculations.
    
    Args:
        date: Datetime object with timezone information
        latitude: Observer latitude
        longitude: Observer longitude
        timezone_str: Timezone string (default: Asia/Kolkata)
        
    Returns:
        Dictionary with nakshatra and pada information
    """
    try:
        # Convert date to Julian day
        jd = swe.julday(date.year, date.month, date.day, 
                        date.hour + date.minute / 60 + date.second / 3600)
        
        # Calculate moon longitude (tropical)
        moon_data = swe.calc_ut(jd, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SPEED)
        moon_long_tropical = moon_data[0][0]  # Tropical longitude
        
        # Calculate ayanamsa (precession correction)
        ayanamsa = swe.get_ayanamsa(jd)
        
        # Calculate sidereal moon longitude
        moon_long = moon_long_tropical - ayanamsa
        if moon_long < 0:
            moon_long += 360
        
        # Calculate nakshatra number and degrees within nakshatra
        nakshatra_span = 360 / 27
        nakshatra_num = int(moon_long / nakshatra_span)
        degrees_in_nakshatra = moon_long % nakshatra_span
        
        # Calculate pada (quarter) within nakshatra
        pada = int(degrees_in_nakshatra / (nakshatra_span / 4)) + 1
        
        # Get nakshatra information
        nakshatra_info = next((n for n in NAKSHATRAS if n["number"] == nakshatra_num + 1), None)
        if not nakshatra_info:
            return {"error": f"Could not determine nakshatra for longitude {moon_long}"}
        
        # Calculate when moon entered current nakshatra
        jd_start = jd
        step_size = 1/24  # 1-hour steps
        while True:
            prev_pos = swe.calc_ut(jd_start, swe.MOON, swe.FLG_SWIEPH)[0][0] - ayanamsa
            if prev_pos < 0:
                prev_pos += 360
            prev_nak = int(prev_pos / nakshatra_span)
            if prev_nak != nakshatra_num:
                jd_start -= step_size  # Step back to the boundary
                break
            jd_start -= step_size
            if jd - jd_start > 2:  # Safety check - don't search more than 2 days back
                break
        
        # Calculate when moon will leave current nakshatra
        jd_end = jd
        step_size = 1/24  # 1-hour steps
        while True:
            next_pos = swe.calc_ut(jd_end, swe.MOON, swe.FLG_SWIEPH)[0][0] - ayanamsa
            if next_pos < 0:
                next_pos += 360
            next_nak = int(next_pos / nakshatra_span)
            if next_nak != nakshatra_num:
                jd_end += step_size  # Step forward to the boundary
                break
            jd_end += step_size
            if jd_end - jd > 2:  # Safety check - don't search more than 2 days ahead
                break
        
        # Convert Julian dates to datetime objects
        start_time_utc = swe.revjul(jd_start)
        end_time_utc = swe.revjul(jd_end)
        
        # Format as datetime objects
        tz = pytz.timezone(timezone_str)
        start_time = datetime(start_time_utc[0], start_time_utc[1], start_time_utc[2], 
                              int(start_time_utc[3]), int((start_time_utc[3] % 1) * 60), 
                              tzinfo=pytz.utc).astimezone(tz)
        end_time = datetime(end_time_utc[0], end_time_utc[1], end_time_utc[2], 
                            int(end_time_utc[3]), int((end_time_utc[3] % 1) * 60), 
                            tzinfo=pytz.utc).astimezone(tz)
        
        # Create nakshatra information
        result = {
            "nakshatra": nakshatra_info["name"],
            "number": nakshatra_info["number"],
            "ruler": nakshatra_info["ruler"],
            "deity": nakshatra_info["deity"],
            "symbol": nakshatra_info["symbol"],
            "qualities": nakshatra_info["qualities"],
            "description": nakshatra_info["description"],
            "degrees_in_nakshatra": round(degrees_in_nakshatra, 2),
            "degrees_remaining": round(nakshatra_span - degrees_in_nakshatra, 2),
            "pada": pada,
            "moon_longitude": round(moon_long, 2),
            "moon_longitude_tropical": round(moon_long_tropical, 2),
            "start_time": start_time.strftime("%I:%M %p, %d %B %Y"),
            "end_time": end_time.strftime("%I:%M %p, %d %B %Y"),
            "calculation_time": datetime.now(tz).strftime("%I:%M %p, %d %B %Y %Z")
        }
        
        return result
    except Exception as e:
        logger.error(f"Error calculating nakshatra: {str(e)}", exc_info=True)
        return {"error": f"Failed to calculate nakshatra: {str(e)}"}

def get_choghadiya_data(date_str=None, latitude=23.0225, longitude=72.5714, 
                      timezone_str="Asia/Kolkata", language="English"):
    """
    Calculate Panchang data including Choghadiya, Hora, Nakshatra, Rahu Kaal,
    Tithi, Yoga and Subh Muhurat for a given date and location
    
    Args:
        date_str: Date string in format YYYY-MM-DD (default: today)
        latitude: Location latitude (default: Ahmedabad)
        longitude: Location longitude (default: Ahmedabad)
        timezone_str: Timezone string (default: Asia/Kolkata)
        language: Language for translation (default: English)
        
    Returns:
        Dictionary with Panchang information
    """
    try:
        # Parse date or use today
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                logger.error(f"Invalid date format: {date_str}")
                date_obj = datetime.now(pytz.timezone(timezone_str)).date()
        else:
            date_obj = datetime.now(pytz.timezone(timezone_str)).date()
        
        # Create location object
        city = LocationInfo(name="Location", region="", timezone=timezone_str,
                            latitude=latitude, longitude=longitude)
        
        # Get sun times
        s = sun(city.observer, date=date_obj, tzinfo=pytz.timezone(timezone_str))
        sunrise = s["sunrise"]
        sunset = s["sunset"]
        
        s_next = sun(city.observer, date=date_obj + timedelta(days=1), tzinfo=pytz.timezone(timezone_str))
        next_sunrise = s_next["sunrise"]
        
        # Calculate durations
        day_duration = (sunset - sunrise) / 8  # For Choghadiya
        night_duration = (next_sunrise - sunset) / 8  # For Choghadiya
        
        day_hora_duration = (sunset - sunrise) / 12  # For Hora/Subh Hora
        night_hora_duration = (next_sunrise - sunset) / 12  # For Hora/Subh Hora
        
        # Get day lord
        weekday = date_obj.weekday()
        day_lord = WEEKDAY_TO_PLANET[weekday]
        start_index = HORA_SEQUENCE.index(day_lord)
        
        # Get Julian day for astronomical calculations
        dt_noon = datetime.combine(date_obj, datetime.min.time().replace(hour=12))
        dt_noon = pytz.timezone(timezone_str).localize(dt_noon)
        jd_noon = swe.julday(dt_noon.year, dt_noon.month, dt_noon.day, 
                             dt_noon.hour + dt_noon.minute/60 + dt_noon.second/3600)
        
        # Get nakshatra information
        nakshatra_info = get_nakshatra_info(dt_noon, latitude, longitude, timezone_str)
        
        # Calculate Tithi and Yoga
        tithi_info = calculate_tithi(jd_noon, timezone_str)
        yoga_info = calculate_yoga(jd_noon, timezone_str)
        
        # Calculate Rahu Kaal, Gulika Kaal, and Yamaghanta
        rahu_kaal = calculate_rahu_kaal(date_obj, sunrise, sunset)
        gulika_kaal = calculate_gulika_kaal(date_obj, sunrise, sunset)
        yamaghanta = calculate_yamaghanta(date_obj, sunrise, sunset)
        
        # Calculate Subh Muhurats
        subh_muhurats = calculate_subh_muhurats(date_obj, sunrise, sunset)
        
        # Create response structure
        result = {
            "day_info": {
                "date": date_obj.strftime("%d %B %Y"),
                "day": date_obj.strftime("%A"),
                "sunrise": sunrise.strftime("%I:%M %p"),
                "sunset": sunset.strftime("%I:%M %p"),
                "day_lord": day_lord
            },
            "tithi": tithi_info,
            "yoga": yoga_info,
            "nakshatra": nakshatra_info,
            "inauspicious_periods": {
                "rahu_kaal": rahu_kaal,
                "gulika_kaal": gulika_kaal,
                "yamaghanta": yamaghanta
            },
            "subh_muhurats": subh_muhurats,
            "day_choghadiya": [],
            "night_choghadiya": [],
            "day_hora": [],
            "night_hora": []
        }
        
        # Calculate day Choghadiya segments
        for i in range(8):
            start = sunrise + i * day_duration
            end = start + day_duration
            planet = HORA_SEQUENCE[(start_index + i) % 7]
            choghadiya = PLANET_TO_CHOGHADIYA[planet]["name"]
            nature = PLANET_TO_CHOGHADIYA[planet]["nature"]
            meaning = CHOGHADIYA_MEANINGS.get(choghadiya, "")
            
            segment = {
                "start_time": start.strftime("%I:%M %p"),
                "end_time": end.strftime("%I:%M %p"),
                "planet": planet,
                "name": choghadiya,
                "nature": nature,
                "meaning": meaning
            }
            result["day_choghadiya"].append(segment)
        
        # Calculate night Choghadiya segments
        for i in range(8):
            start = sunset + i * night_duration
            end = start + night_duration
            planet = HORA_SEQUENCE[(start_index + i + 1) % 7]
            choghadiya = PLANET_TO_CHOGHADIYA[planet]["name"]
            nature = PLANET_TO_CHOGHADIYA[planet]["nature"]
            meaning = CHOGHADIYA_MEANINGS.get(choghadiya, "")
            
            segment = {
                "start_time": start.strftime("%I:%M %p"),
                "end_time": end.strftime("%I:%M %p"),
                "planet": planet,
                "name": choghadiya,
                "nature": nature,
                "meaning": meaning
            }
            result["night_choghadiya"].append(segment)
        
        # Calculate day Hora segments (Subh Hora)
        for i in range(12):
            start = sunrise + i * day_hora_duration
            end = start + day_hora_duration
            
            hora_planet = HORA_SEQUENCE[(HORA_SEQUENCE.index(day_lord) + i) % 7]
            
            # Get nature and meaning for this planet
            nature = PLANET_HORA_PROPERTIES[hora_planet]["nature"]
            meaning = PLANET_HORA_PROPERTIES[hora_planet]["meaning"]
            
            segment = {
                "start_time": start.strftime("%I:%M %p"),
                "end_time": end.strftime("%I:%M %p"),
                "planet": hora_planet,
                "nature": nature,
                "meaning": meaning
            }
            result["day_hora"].append(segment)
        
        # Calculate night Hora segments (Subh Hora)
        for i in range(12):
            start = sunset + i * night_hora_duration
            end = start + night_hora_duration
            
            hora_planet = HORA_SEQUENCE[(HORA_SEQUENCE.index(day_lord) + 12 + i) % 7]
            
            # Get nature and meaning for this planet
            nature = PLANET_HORA_PROPERTIES[hora_planet]["nature"]
            meaning = PLANET_HORA_PROPERTIES[hora_planet]["meaning"]
            
            segment = {
                "start_time": start.strftime("%I:%M %p"),
                "end_time": end.strftime("%I:%M %p"),
                "planet": hora_planet,
                "nature": nature,
                "meaning": meaning
            }
            result["night_hora"].append(segment)
        
        # Translate if needed using manual translation
        if language.lower() in ["hindi", "gujarati"]:
            try:
                # Translate day info
                result["day_info"]["day"] = translate_panchang_text(result["day_info"]["day"], language)
                
                # Properly translate the date with month name
                date_parts = result["day_info"]["date"].split()
                if len(date_parts) == 3:  # Should be [day, month, year]
                    day_num = date_parts[0]
                    month_name = date_parts[1]
                    year_num = date_parts[2]
                    
                    # Translate day and year numbers
                    day_num_translated = translate_numbers_to_script(day_num, language)
                    year_num_translated = translate_numbers_to_script(year_num, language)
                    
                    # Translate month name
                    month_name_translated = translate_panchang_text(month_name, language)
                    
                    # Reconstruct the date
                    result["day_info"]["date"] = f"{day_num_translated} {month_name_translated} {year_num_translated}"
                else:
                    # Fallback to just translating numbers if the format is unexpected
                    result["day_info"]["date"] = translate_numbers_to_script(result["day_info"]["date"], language)
                
                result["day_info"]["sunrise"] = translate_numbers_to_script(result["day_info"]["sunrise"], language)
                result["day_info"]["sunset"] = translate_numbers_to_script(result["day_info"]["sunset"], language)
                result["day_info"]["day_lord"] = translate_panchang_text(result["day_info"]["day_lord"], language)
                
                # Translate Choghadiya meanings and natures
                for segment in result["day_choghadiya"] + result["night_choghadiya"]:
                    segment["name"] = translate_panchang_text(segment["name"], language)
                    segment["nature"] = translate_panchang_text(segment["nature"], language)
                    segment["meaning"] = translate_panchang_text(segment["meaning"], language)
                    segment["planet"] = translate_panchang_text(segment["planet"], language)
                    segment["start_time"] = translate_numbers_to_script(segment["start_time"], language)
                    segment["end_time"] = translate_numbers_to_script(segment["end_time"], language)
                
                # Translate Hora meanings and natures
                for segment in result["day_hora"] + result["night_hora"]:
                    segment["nature"] = translate_panchang_text(segment["nature"], language)
                    segment["meaning"] = translate_panchang_text(segment["meaning"], language)
                    segment["planet"] = translate_panchang_text(segment["planet"], language)
                    segment["start_time"] = translate_numbers_to_script(segment["start_time"], language)
                    segment["end_time"] = translate_numbers_to_script(segment["end_time"], language)
                
                # Translate inauspicious periods
                for period_name in ["rahu_kaal", "gulika_kaal", "yamaghanta"]:
                    if period_name in result["inauspicious_periods"]:
                        period = result["inauspicious_periods"][period_name]
                        period["start_time"] = translate_numbers_to_script(period["start_time"], language)
                        period["end_time"] = translate_numbers_to_script(period["end_time"], language)
                        if "description" in period:
                            period["description"] = translate_panchang_text(period["description"], language)
                        # Also translate duration_minutes field
                        if "duration_minutes" in period:
                            period["duration_minutes"] = translate_numbers_to_script(str(period["duration_minutes"]), language)
                
                # Translate subh muhurats
                for muhurat in result["subh_muhurats"]:
                    muhurat["name"] = translate_panchang_text(muhurat["name"], language)
                    muhurat["description"] = translate_panchang_text(muhurat["description"], language)
                    muhurat["start_time"] = translate_numbers_to_script(muhurat["start_time"], language)
                    muhurat["end_time"] = translate_numbers_to_script(muhurat["end_time"], language)
                    # Also translate duration_minutes field
                    if "duration_minutes" in muhurat:
                        muhurat["duration_minutes"] = translate_numbers_to_script(str(muhurat["duration_minutes"]), language)
                
                # Translate tithi information
                tithi_translatable_fields = ["name", "paksha", "deity", "description","special"]
                for field in tithi_translatable_fields:
                    if field in result["tithi"]:
                        result["tithi"][field] = translate_panchang_text(result["tithi"][field], language)
                # Translate number field in tithi
                if "number" in result["tithi"]:
                    result["tithi"]["number"] = translate_numbers_to_script(str(result["tithi"]["number"]), language)
                
                # Translate yoga information
                yoga_translatable_fields = ["name", "meaning", "speciality"]
                for field in yoga_translatable_fields:
                    if field in result["yoga"]:
                        result["yoga"][field] = translate_panchang_text(result["yoga"][field], language)
                # Translate number field in yoga
                if "number" in result["yoga"]:
                    result["yoga"]["number"] = translate_numbers_to_script(str(result["yoga"]["number"]), language)
                
                # Better translation for nakshatra information
                if "nakshatra" in result:
                    nak_info = result["nakshatra"]
                    
                    # First translate text fields
                    text_fields = ["ruler", "deity", "symbol", "qualities", "description"]
                    for field in text_fields:
                        if field in nak_info:
                            nak_info[field] = translate_panchang_text(nak_info[field], language)
                    
                    # Special handling for nakshatra name - use the dictionary mapping directly
                    if "nakshatra" in nak_info:
                        nakshatra_name = nak_info["nakshatra"]
                        translations = PANCHANG_TRANSLATIONS.get(language.lower(), {})
                        if nakshatra_name in translations:
                            nak_info["nakshatra"] = translations[nakshatra_name]
                        else:
                            nak_info["nakshatra"] = translate_panchang_text(nakshatra_name, language)
                    
                    # Translate time fields with proper month handling
                    time_fields = ["start_time", "end_time", "calculation_time"]
                    for time_field in time_fields:
                        if time_field in nak_info:
                            time_parts = nak_info[time_field].split(", ")
                            if len(time_parts) == 2:
                                time_value = time_parts[0]
                                date_value = time_parts[1]
                                
                                # Translate time value numbers
                                time_value_translated = translate_numbers_to_script(time_value, language)
                                
                                # Handle date with month
                                date_components = date_value.split()
                                if len(date_components) >= 3:  # Should have day, month, year
                                    day = date_components[0]
                                    month = date_components[1]
                                    year = date_components[2]
                                    
                                    # Translate day and year
                                    day_translated = translate_numbers_to_script(day, language)
                                    year_translated = translate_numbers_to_script(year, language)
                                    
                                    # Translate month
                                    month_translated = translate_panchang_text(month, language)
                                    
                                    # Handle potential timezone at the end
                                    timezone_part = ""
                                    if len(date_components) > 3:
                                        timezone = date_components[3]
                                        timezone_part = " " + translate_panchang_text(timezone, language)
                                    
                                    # Reconstruct date value
                                    date_value_translated = f"{day_translated} {month_translated} {year_translated}{timezone_part}"
                                    
                                    # Reconstruct full time field
                                    nak_info[time_field] = f"{time_value_translated}, {date_value_translated}"
                                else:
                                    # Just translate the numbers if format is unexpected
                                    nak_info[time_field] = translate_numbers_to_script(nak_info[time_field], language)
                            else:
                                # Just translate the numbers if format is unexpected
                                nak_info[time_field] = translate_numbers_to_script(nak_info[time_field], language)
                    
                    # Translate number fields
                    number_fields = ["number", "pada", "degrees_in_nakshatra", "degrees_remaining", 
                                    "moon_longitude", "moon_longitude_tropical"]
                    for num_field in number_fields:
                        if num_field in nak_info:
                            nak_info[num_field] = translate_numbers_to_script(str(nak_info[num_field]), language)
                
                logger.info(f"Translated Panchang data to {language}")
            except Exception as e:
                logger.error(f"Translation error: {str(e)}")
                result["translation_error"] = f"Some translations may be incomplete: {str(e)}"
        
        return result
    except Exception as e:
        logger.error(f"Error calculating Panchang: {str(e)}", exc_info=True)
        return {"error": f"Failed to calculate Panchang: {str(e)}"}

def calculate_tithi(jd: float, timezone_str: str = "Asia/Kolkata") -> Dict:
    """
    Calculate the Tithi (lunar day) for a given Julian day.
    Tithi is based on the angle between the moon and the sun.
    """
    try:
        # Calculate sun and moon longitudes
        sun_data = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)
        moon_data = swe.calc_ut(jd, swe.MOON, swe.FLG_SWIEPH)
        
        sun_long = sun_data[0][0]
        moon_long = moon_data[0][0]
        
        # Calculate the angular difference
        diff = moon_long - sun_long
        if diff < 0:
            diff += 360
        
        # Each tithi spans 12 degrees
        tithi_num = int(diff / 12) + 1
        if tithi_num > 30:
            tithi_num = 30
        
        # Get tithi information
        tithi_info = next((t for t in TITHIS if t["number"] == tithi_num), TITHIS[0])
        
        return {
            "number": tithi_info["number"],
            "name": tithi_info["name"],
            "paksha": tithi_info["paksha"],
            "deity": tithi_info["deity"],
            "special": tithi_info.get("special"),
            "description": tithi_info["description"]
        }
    except Exception as e:
        logger.error(f"Error calculating tithi: {e}")
        return {"error": f"Failed to calculate tithi: {str(e)}"}

def calculate_yoga(jd: float, timezone_str: str = "Asia/Kolkata") -> Dict:
    """
    Calculate the Yoga for a given Julian day.
    
    Yoga is based on the sum of sun and moon longitudes.
    """
    try:
        # Calculate sun and moon longitudes
        sun_data = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)
        moon_data = swe.calc_ut(jd, swe.MOON, swe.FLG_SWIEPH)
        
        sun_long = sun_data[0][0]
        moon_long = moon_data[0][0]
        
        # Calculate the sum of longitudes
        yoga_value = (sun_long + moon_long) % 360
        
        # Each yoga spans 13°20' (800 arc-minutes)
        yoga_num = int(yoga_value / (800/60)) + 1
        if yoga_num > 27:
            yoga_num = 27
        
        # Get yoga information
        yoga_info = next((y for y in YOGAS if y["number"] == yoga_num), YOGAS[0])
        
        return {
            "number": yoga_info["number"],
            "name": yoga_info["name"],
            "meaning": yoga_info["meaning"],
            "speciality": yoga_info["speciality"]
        }
    except Exception as e:
        logger.error(f"Error calculating yoga: {e}")
        return {"error": f"Failed to calculate yoga: {str(e)}"}

def calculate_rahu_kaal(date_obj: date, sunrise: datetime, sunset: datetime) -> Dict:
    """Calculate Rahu Kaal timing for a given date."""
    weekday = date_obj.weekday()
    rahu_segments = {0: 7, 1: 1, 2: 6, 3: 5, 4: 4, 5: 3, 6: 2}
    
    day_duration = sunset - sunrise
    segment_duration = day_duration / 8
    
    rahu_segment = rahu_segments[weekday]
    rahu_start = sunrise + (segment_duration * (rahu_segment - 1))
    rahu_end = rahu_start + segment_duration
    
    return {
        "start_time": rahu_start.strftime("%I:%M %p"),
        "end_time": rahu_end.strftime("%I:%M %p"),
        "duration_minutes": round(segment_duration.total_seconds() / 60),
        "description": "Rahu Kaal is considered an inauspicious time for starting important activities."
    }

def calculate_gulika_kaal(date_obj: date, sunrise: datetime, sunset: datetime) -> Dict:
    """Calculate Gulika Kaal timing for a given date."""
    weekday = date_obj.weekday()
    gulika_segments = {0: 6, 1: 5, 2: 4, 3: 3, 4: 2, 5: 1, 6: 0}
    
    day_duration = sunset - sunrise
    segment_duration = day_duration / 8
    
    gulika_segment = gulika_segments[weekday]
    gulika_start = sunrise + (segment_duration * gulika_segment)
    gulika_end = gulika_start + segment_duration
    
    return {
        "start_time": gulika_start.strftime("%I:%M %p"),
        "end_time": gulika_end.strftime("%I:%M %p"),
        "duration_minutes": round(segment_duration.total_seconds() / 60),
        "description": "Gulika Kaal is considered an unfavorable time period."
    }

def calculate_yamaghanta(date_obj: date, sunrise: datetime, sunset: datetime) -> Dict:
    """Calculate Yamaghanta timing for a given date."""
    weekday = date_obj.weekday()
    yama_segments = {0: 4, 1: 3, 2: 2, 3: 1, 4: 0, 5: 6, 6: 5}
    
    day_duration = sunset - sunrise
    segment_duration = day_duration / 8
    
    yama_segment = yama_segments[weekday]
    yama_start = sunrise + (segment_duration * yama_segment)
    yama_end = yama_start + segment_duration
    
    return {
        "start_time": yama_start.strftime("%I:%M %p"),
        "end_time": yama_end.strftime("%I:%M %p"),
        "duration_minutes": round(segment_duration.total_seconds() / 60),
        "description": "Yamaghanta is considered inauspicious for important activities."
    }

def calculate_subh_muhurats(date_obj: date, sunrise: datetime, sunset: datetime) -> List[Dict]:
    """Calculate auspicious muhurats for a given date."""
    subh_muhurats = []
    
    # Brahma Muhurat
    brahma_end = sunrise - timedelta(minutes=24)
    brahma_start = brahma_end - timedelta(minutes=72)
    subh_muhurats.append({
        "name": "Brahma Muhurat",
        "start_time": brahma_start.strftime("%I:%M %p"),
        "end_time": brahma_end.strftime("%I:%M %p"),
        "duration_minutes": 72,
        "description": "Sacred early morning hours ideal for spiritual practices."
    })
    
    # Abhijit Muhurat
    solar_noon = sunrise + (sunset - sunrise) / 2
    abhijit_start = solar_noon - timedelta(minutes=24)
    abhijit_end = solar_noon + timedelta(minutes=24)
    subh_muhurats.append({
        "name": "Abhijit Muhurat",
        "start_time": abhijit_start.strftime("%I:%M %p"),
        "end_time": abhijit_end.strftime("%I:%M %p"),
        "duration_minutes": 48,
        "description": "Highly auspicious for starting new ventures."
    })
    
    return subh_muhurats

@app.post("/horoscope")
async def horoscope_endpoint(request: HoroscopeRequest):
    """API endpoint to generate horoscope predictions"""
    start_time = time.time()
    
    try:
        # Extract parameters from request
        zodiac_sign = request.zodiac_sign
        language = request.language
        prediction_type = request.type
        latitude = float(request.location.get('latitude', 0.0))
        longitude = float(request.location.get('longitude', 0.0))
        
        logger.info(f"Horoscope request: {zodiac_sign}, {prediction_type}, {language}")
        
        # Validate zodiac sign
        if not zodiac_sign or zodiac_sign not in ZODIAC_SIGNS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid zodiac sign. Please provide one of: {', '.join(ZODIAC_SIGNS)}"
            )
        
        # Validate language
        valid_languages = ["English", "Hindi", "Gujarati"]
        if language not in valid_languages:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid language. Please provide one of: {', '.join(valid_languages)}"
            )
        
        # Generate horoscope asynchronously
        horoscope = await asyncio.to_thread(
            generate_horoscope, 
            zodiac_sign, 
            language, 
            prediction_type, 
            latitude, 
            longitude
        )
        
        # Log performance metrics
        execution_time = time.time() - start_time
        logger.info(f"Horoscope generated in {execution_time:.2f} seconds")
        
        return horoscope
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing your request: {str(e)}"
        )

@app.post("/panchang")
async def panchang_endpoint(request: PanchangRequest):
    """API endpoint to get Panchang information (Choghadiya and Hora)"""
    try:
        # Extract parameters from request
        date_str = request.date
        language = request.language
        latitude = request.latitude
        longitude = request.longitude
        timezone_str = request.timezone
        
        logger.info(f"Panchang request: date={date_str}, lat={latitude}, lon={longitude}, language={language}")
        
        # Validate language
        valid_languages = ["English", "Hindi", "Gujarati"]
        if language not in valid_languages:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid language. Please provide one of: {', '.join(valid_languages)}"
            )
        
        # Calculate Panchang data (Choghadiya and Hora) asynchronously
        result = await asyncio.to_thread(
            get_choghadiya_data,
            date_str=date_str,
            latitude=latitude,
            longitude=longitude,
            timezone_str=timezone_str,
            language=language
        )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing your request: {str(e)}"
        )
if __name__ == "__main__":
    import uvicorn
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Horoscope and Panchang API Server')
    parser.add_argument('--host', default=os.environ.get('HOROSCOPE_HOST', '0.0.0.0'),
                       help='Host to bind the server to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=int(os.environ.get('HOROSCOPE_PORT', 8000)),
                       help='Port to bind the server to (default: 8000)')
    parser.add_argument('--log-level', default=os.environ.get('LOG_LEVEL', 'INFO'),
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Set the logging level')
    parser.add_argument('--ephe-path', default=os.environ.get('EPHE_PATH', '/path/to/ephemeris'),
                       help='Path to the ephemeris files')
    
    args = parser.parse_args()
    
    # Configure logging
    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {args.log_level}')
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure ephemeris path
    if os.path.exists(args.ephe_path):
        swe.set_ephe_path(args.ephe_path)
        logger.info(f"Ephemeris path set to: {args.ephe_path}")
    else:
        logger.warning(f"Ephemeris path not found: {args.ephe_path}")
    
    try:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level=args.log_level.lower()
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")

"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import MyCoordinator
from .entity import RbfaEntity

import logging

_LOGGER = logging.getLogger(__name__)

# Mapping langue -> mot clé URL pour le match
MATCH_URL_KEYWORDS = {
    'nl': 'wedstrijd',
    'fr': 'match',
    'en': 'game',
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RBFA sensor based on a config entry."""
    coordinator: MyCoordinator = hass.data[DOMAIN][entry.entry_id]
    team_id = entry.data.get('team')
    
    # Récupérer la langue depuis la config (data ou options)
    language = entry.options.get('language') or entry.data.get('language', 'nl')

    # Créer exactement 3 entités
    entities = [
        RbfaTeamSensor(coordinator, entry, team_id),
        RbfaMatchSensor(coordinator, entry, team_id, "last", language),
        RbfaMatchSensor(coordinator, entry, team_id, "upcoming", language),
    ]

    async_add_entities(entities)


class RbfaTeamSensor(RbfaEntity, SensorEntity):
    """Représente l'équipe configurée."""

    def __init__(
        self,
        coordinator: MyCoordinator,
        entry: ConfigEntry,
        team_id: str,
    ) -> None:
        """Initialize the team sensor."""
        super().__init__(coordinator)
        self.team_id = team_id
        
        # Récupérer le nom alternatif depuis data ou options
        alt_name = entry.options.get('alt_name') or entry.data.get('alt_name')
        self._attr_name = alt_name if alt_name else f"Team {team_id}"
        
        self._attr_unique_id = f"{DOMAIN}_team_{team_id}"
        self._attr_icon = "mdi:shield-account"

    @property
    def native_value(self) -> str | None:
        """Return the team name."""
        return self._attr_name

    @property
    def entity_picture(self) -> str | None:
        """Return the team logo."""
        data = self.coordinator.data.get('upcoming') or self.coordinator.data.get('lastmatch')
        if not data:
            return None
        
        # Détermine si c'est l'équipe à domicile ou extérieure
        if data.get('hometeamid') == self.team_id:
            return data.get('hometeamlogo')
        elif data.get('awayteamid') == self.team_id:
            return data.get('awayteamlogo')
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return team attributes."""
        return {
            'team_id': self.team_id,
            'integration': 'RBFA',
        }


class RbfaMatchSensor(RbfaEntity, SensorEntity):
    """Représente un match (dernier ou prochain)."""

    def __init__(
        self,
        coordinator: MyCoordinator,
        entry: ConfigEntry,
        team_id: str,
        match_type: str,
        language: str = 'nl',
    ) -> None:
        """Initialize the match sensor.
        
        Args:
            match_type: "last" pour dernier match, "upcoming" pour prochain match
            language: Code langue pour l'URL (nl, fr, en)
        """
        super().__init__(coordinator)
        self.team_id = team_id
        self.match_type = match_type
        self.language = language
        
        # Déterminer la clé de données en fonction du type
        self._data_key = "lastmatch" if match_type == "last" else "upcoming"
        
        # Récupérer le nom alternatif
        alt_name = entry.options.get('alt_name') or entry.data.get('alt_name')
        team_name = alt_name if alt_name else 'Team'
        
        # Configuration du nom et de l'icône
        if match_type == "last":
            self._attr_name = f"{team_name} - Dernier Match"
            self._attr_icon = "mdi:history"
        else:
            self._attr_name = f"{team_name} - Prochain Match"
            self._attr_icon = "mdi:calendar-clock"
        
        self._attr_unique_id = f"{DOMAIN}_{match_type}_match_{team_id}"

    def _get_match_url(self, match_id: str) -> str:
        """Génère l'URL du match en fonction de la langue configurée."""
        keyword = MATCH_URL_KEYWORDS.get(self.language, 'wedstrijd')
        return f"https://www.rbfa.be/{self.language}/{keyword}/{match_id}"

    @property
    def native_value(self) -> str | None:
        """Return match status or score."""
        data = self.coordinator.data.get(self._data_key)
        if not data:
            return "Aucun match"
        
        home = data.get('hometeam', '?')
        away = data.get('awayteam', '?')
        
        # Pour le dernier match, afficher le score si disponible
        if self.match_type == "last":
            home_goals = data.get('hometeamgoals')
            away_goals = data.get('awayteamgoals')
            if home_goals is not None and away_goals is not None:
                return f"{home} {home_goals} - {away_goals} {away}"
        
        # Pour le prochain match ou si pas de score
        return f"{home} vs {away}"

    @property
    def entity_picture(self) -> str | None:
        """Return the logo of our team."""
        data = self.coordinator.data.get(self._data_key)
        if not data:
            return None
        
        # Retourner le logo de notre équipe
        if data.get('hometeamid') == self.team_id:
            return data.get('hometeamlogo')
        elif data.get('awayteamid') == self.team_id:
            return data.get('awayteamlogo')
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return match attributes."""
        data = self.coordinator.data.get(self._data_key)
        if not data:
            return {
                'match_type': self.match_type,
                'status': 'unavailable',
                'language': self.language,
            }
        
        match_id = data.get('matchid')
        
        attributes = {
            'match_type': self.match_type,
            'language': self.language,
            'match_id': match_id,
            'series': data.get('series'),
            
            # Équipe à domicile
            'domicile': data.get('hometeam'),
            'domicile_id': data.get('hometeamid'),
            'domicile_logo': data.get('hometeamlogo'),
            'domicile_position': data.get('hometeamposition'),
            
            # Équipe extérieure
            'exterieur': data.get('awayteam'),
            'exterieur_id': data.get('awayteamid'),
            'exterieur_logo': data.get('awayteamlogo'),
            'exterieur_position': data.get('awayteamposition'),
            
            # Détails du match
            'heure': data.get('starttime'),
            'date_fin': data.get('endtime'),
            'localisation': data.get('location'),
            'arbitre': data.get('referee'),
            
            # URL du match avec la bonne langue
            'match_url': self._get_match_url(match_id) if match_id else None,
        }
        
        # Ajouter le score pour le dernier match
        if self.match_type == "last":
            attributes['domicile_score'] = data.get('hometeamgoals')
            attributes['exterieur_score'] = data.get('awayteamgoals')
            attributes['domicile_penalties'] = data.get('hometeampenalties')
            attributes['exterieur_penalties'] = data.get('awayteampenalties')
        
        # Ajouter le classement si disponible
        if data.get('ranking'):
            attributes['classement'] = data.get('ranking')
        
        # Ajouter le channel (ACFF/VV)
        if data.get('channel'):
            attributes['channel'] = data.get('channel')
            attributes['channel_logo'] = f"https://www.rbfa.be/assets/img/icons/organisers/Logo{data.get('channel').upper()}.svg"
        
        return attributes

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

    # Créer les 7 entités
    entities = [
        RbfaTeamSensor(coordinator, entry, team_id),
        RbfaMatchInfoSensor(coordinator, entry, team_id, "upcoming", language),
        RbfaMatchTeamSensor(coordinator, entry, team_id, "upcoming", "home", language),
        RbfaMatchTeamSensor(coordinator, entry, team_id, "upcoming", "away", language),
        RbfaMatchInfoSensor(coordinator, entry, team_id, "last", language),
        RbfaMatchTeamSensor(coordinator, entry, team_id, "last", "home", language),
        RbfaMatchTeamSensor(coordinator, entry, team_id, "last", "away", language),
    ]

    async_add_entities(entities)


class RbfaTeamSensor(RbfaEntity, SensorEntity):
    """Représente l'équipe configurée (MyTeam)."""

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
        
        self._attr_unique_id = f"{DOMAIN}_myteam_{team_id}"
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
        data = self.coordinator.data.get('upcoming') or self.coordinator.data.get('lastmatch')
        
        attributes = {
            'team_id': self.team_id,
            'integration': 'RBFA',
        }
        
        if data:
            attributes['serie'] = data.get('series')
            
            # Channel logo
            if data.get('channel'):
                attributes['channel'] = data.get('channel')
                attributes['channel_logo'] = f"https://www.rbfa.be/assets/img/icons/organisers/Logo{data.get('channel').upper()}.svg"
        
        return attributes


class RbfaMatchInfoSensor(RbfaEntity, SensorEntity):
    """Représente les informations générales d'un match (arbitre, lieu, date)."""

    def __init__(
        self,
        coordinator: MyCoordinator,
        entry: ConfigEntry,
        team_id: str,
        match_type: str,
        language: str = 'nl',
    ) -> None:
        """Initialize the match info sensor.
        
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
        
        # Configuration du nom et de l'icône
        if match_type == "last":
            self._attr_name = "Last Match Info"
            self._attr_icon = "mdi:information"
        else:
            self._attr_name = "Next Match Info"
            self._attr_icon = "mdi:information-outline"
        
        self._attr_unique_id = f"{DOMAIN}_{match_type}_match_info_{team_id}"

    def _get_match_url(self, match_id: str) -> str:
        """Génère l'URL du match en fonction de la langue configurée."""
        keyword = MATCH_URL_KEYWORDS.get(self.language, 'wedstrijd')
        return f"https://www.rbfa.be/{self.language}/{keyword}/{match_id}"

    @property
    def native_value(self) -> str | None:
        """Return match date and time."""
        data = self.coordinator.data.get(self._data_key)
        if not data:
            return "Aucun match"
        
        start_time = data.get('starttime')
        if start_time:
            return str(start_time)
        
        return "Date inconnue"

    @property
    def extra_state_attributes(self) -> dict:
        """Return match info attributes."""
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
            'serie': data.get('series'),
            
            # Détails du match
            'date': data.get('starttime'),
            'heure': data.get('starttime'),
            'date_fin': data.get('endtime'),
            'localisation': data.get('location'),
            'arbitre': data.get('referee'),
            
            # URL du match avec la bonne langue
            'match_url': self._get_match_url(match_id) if match_id else None,
        }
        
        # Ajouter le classement si disponible
        if data.get('ranking'):
            attributes['classement'] = data.get('ranking')
        
        # Ajouter le channel (ACFF/VV)
        if data.get('channel'):
            attributes['channel'] = data.get('channel')
            attributes['channel_logo'] = f"https://www.rbfa.be/assets/img/icons/organisers/Logo{data.get('channel').upper()}.svg"
        
        return attributes


class RbfaMatchTeamSensor(RbfaEntity, SensorEntity):
    """Représente une équipe dans un match (domicile ou extérieur)."""

    def __init__(
        self,
        coordinator: MyCoordinator,
        entry: ConfigEntry,
        team_id: str,
        match_type: str,
        side: str,
        language: str = 'nl',
    ) -> None:
        """Initialize the match team sensor.
        
        Args:
            match_type: "last" pour dernier match, "upcoming" pour prochain match
            side: "home" pour domicile, "away" pour extérieur
            language: Code langue pour l'URL (nl, fr, en)
        """
        super().__init__(coordinator)
        self.team_id = team_id
        self.match_type = match_type
        self.side = side
        self.language = language
        
        # Déterminer la clé de données en fonction du type
        self._data_key = "lastmatch" if match_type == "last" else "upcoming"
        
        # Configuration du nom et de l'icône
        side_name = "Domicile" if side == "home" else "Extérieur"
        if match_type == "last":
            self._attr_name = f"Last Match {side_name}"
            self._attr_icon = "mdi:home" if side == "home" else "mdi:airplane-takeoff"
        else:
            self._attr_name = f"Next Match {side_name}"
            self._attr_icon = "mdi:home-outline" if side == "home" else "mdi:airplane"
        
        self._attr_unique_id = f"{DOMAIN}_{match_type}_match_{side}_{team_id}"

    @property
    def native_value(self) -> str | None:
        """Return team name."""
        data = self.coordinator.data.get(self._data_key)
        if not data:
            return "Aucune équipe"
        
        if self.side == "home":
            return data.get('hometeam', '?')
        else:
            return data.get('awayteam', '?')

    @property
    def entity_picture(self) -> str | None:
        """Return the team logo."""
        data = self.coordinator.data.get(self._data_key)
        if not data:
            return None
        
        if self.side == "home":
            return data.get('hometeamlogo')
        else:
            return data.get('awayteamlogo')

    @property
    def extra_state_attributes(self) -> dict:
        """Return team attributes."""
        data = self.coordinator.data.get(self._data_key)
        if not data:
            return {
                'match_type': self.match_type,
                'side': self.side,
                'status': 'unavailable',
            }
        
        prefix = 'hometeam' if self.side == 'home' else 'awayteam'
        
        attributes = {
            'match_type': self.match_type,
            'side': self.side,
            'team_id': data.get(f'{prefix}id'),
            'team_name': data.get(prefix),
            'logo': data.get(f'{prefix}logo'),
            'position': data.get(f'{prefix}position'),
            'serie': data.get('series'),
        }
        
        # Ajouter le score pour le dernier match
        if self.match_type == "last":
            attributes['score'] = data.get(f'{prefix}goals')
            attributes['penalties'] = data.get(f'{prefix}penalties')
        
        # Indiquer si c'est l'équipe configurée
        attributes['is_my_team'] = data.get(f'{prefix}id') == self.team_id
        
        return attributes

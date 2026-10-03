// Human-readable names for manifest keys (README §4). The manifest from
// /meta wins for licence/date/status; this only fills in names and links.
import type { CityId } from '@/api/types'

export const SOURCES: Record<string, { name: string; url?: string; licence?: string }> = {
  osm_krakow: { name: 'OpenStreetMap (Geofabrik, Małopolskie)', url: 'https://www.openstreetmap.org/copyright', licence: 'ODbL' },
  osm_praha: { name: 'OpenStreetMap (Geofabrik, Středočeský kraj)', url: 'https://www.openstreetmap.org/copyright', licence: 'ODbL' },
  basemap: { name: 'OpenFreeMap', url: 'https://openfreemap.org' },
  gtfs_ztp: { name: 'ZTP Kraków – GTFS', url: 'https://gtfs.ztp.krakow.pl/' },
  gtfs_rt_ztp: { name: 'ZTP Kraków – GTFS-RT', url: 'https://gtfs.ztp.krakow.pl/' },
  ztp_hub: { name: 'ZTP Kraków – hub danych', url: 'https://ztpk-gmk-2.hub.arcgis.com/' },
  krk_open: { name: 'Otwarte Dane Kraków', url: 'https://otwartedane.um.krakow.pl/' },
  msip: { name: 'MSIP / UM Kraków', url: 'https://msip.krakow.pl/' },
  safety_krk: { name: 'Bezpieczny Kraków', url: 'https://bezpiecznykrakow-gmk.hub.arcgis.com/' },
  gios: { name: 'GIOŚ – jakość powietrza', url: 'https://powietrze.gios.gov.pl/' },
  men_schools: { name: 'MEN – wykaz szkół (SIO)', url: 'https://dane.gov.pl/pl/dataset/839', licence: 'CC BY 4.0' },
  rcn: { name: 'GUGiK – Rejestr Cen Nieruchomości', url: 'https://www.geoportal.gov.pl/' },
  gtfs_pid: { name: 'PID / ROPID – GTFS', url: 'https://pid.cz/en/opendata/', licence: 'CC BY' },
  golemio: { name: 'Golemio / OICT', url: 'https://api.golemio.cz' },
  praha_open: { name: 'Otevřená data Praha', url: 'https://opendata.praha.eu/' },
  ipr: { name: 'IPR Praha – Geoportál', url: 'https://geoportalpraha.cz/' },
  ruian: { name: 'ČÚZK – RÚIAN', url: 'https://cuzk.gov.cz/ruian/', licence: 'CC BY 4.0' },
  msmt_schools: { name: 'MŠMT – rejstřík škol', url: 'https://rejstriky.msmt.cz/' },
  nrpzs: { name: 'ÚZIS – NRPZS', url: 'https://datanzis.uzis.gov.cz/', licence: 'CC BY 4.0' },
  chmi_air: { name: 'ČHMÚ – kvalita ovzduší', url: 'https://opendata.chmi.cz/air_quality/' },
  police_cz: { name: 'Policie ČR – mapa kriminality', url: 'https://kriminalita.policie.gov.cz/', licence: 'non-commercial' },
  mf_rent: { name: 'MF ČR – cenová mapa nájemného', url: 'https://mf.gov.cz/cenova-mapa-najemneho' },
}

export const CREDITS: Record<CityId, string[]> = {
  krakow: ['OpenStreetMap', 'ZTP Kraków', 'MSIP/UM Kraków', 'GIOŚ', 'MEN', 'GUGiK'],
  praha: ['OpenStreetMap', 'PID/ROPID', 'Golemio/OICT', 'IPR Praha', 'ČÚZK', 'MŠMT', 'ÚZIS', 'ČHMÚ', 'Policie ČR', 'MF ČR'],
}

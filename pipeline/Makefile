# Workstream A — data pipeline.  make data CITY=krakow|praha|all
CITY ?= all
CITIES := $(if $(filter all,$(CITY)),krakow praha,$(CITY))
# r5py needs Java 21 (brew install openjdk@21 is keg-only, so point JAVA_HOME at it)
JAVA_HOME ?= $(shell /usr/libexec/java_home -v 21 2>/dev/null || echo /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home)
export JAVA_HOME
UV := uv run --python 3.12

.PHONY: data fetch build travel ml validate qa clean-interim

data: fetch build travel ml validate

fetch:
	@for c in $(CITIES); do $(UV) python fetch.py --city $$c || exit 1; done

build:
	@for c in $(CITIES); do $(UV) python run.py --city $$c || exit 1; done

travel:
	@for c in $(CITIES); do $(UV) python travel.py --city $$c || exit 1; done

ml:
	$(UV) python ml_features.py

validate:
	@for c in $(CITIES); do $(UV) python validate.py --city $$c || exit 1; done

qa:
	@for c in $(CITIES); do $(UV) python qa.py --city $$c || exit 1; done

clean-interim:
	rm -rf ../data/interim

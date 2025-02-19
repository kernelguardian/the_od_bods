### Setting the environment
import pandas as pd
import os
import datetime as dt


def merge_data():
    ### Loading data

    ### From ckan output
    source_ckan = pd.DataFrame()
    folder = "data/ckan/"
    for dirname, _, filenames in os.walk(folder):
        for filename in filenames:
            if filename.rsplit(".", 1)[1] == "csv":
                print(filename)
                source_ckan = pd.concat(
                    [
                        source_ckan,
                        pd.read_csv(
                            folder + r"/" + filename, parse_dates=["DateCreated","DateUpdated"], lineterminator='\n'
                        ),
                    ]
                )
    source_ckan["Source"] = "ckan API"

    ### From scotgov csv
    source_scotgov = pd.read_csv("data/scotgov-datasets-sparkql.csv")
    source_scotgov = source_scotgov.rename(
        columns={
            "title": "Title",
            "category": "OriginalTags",
            "organization": "Owner",
            "notes": "Description",
            "date_created": "DateCreated",
            "date_updated": "DateUpdated",
            "url": "PageURL",
            "licence":"License"
        }
    )
    source_scotgov["Source"] = "sparql"
    source_scotgov['DateUpdated'] = pd.to_datetime(source_scotgov['DateUpdated'], utc=True).dt.tz_localize(None)
    source_scotgov['DateCreated'] = pd.to_datetime(source_scotgov['DateCreated'], utc=True).dt.tz_localize(None)

    ### From arcgis api
    source_arcgis = pd.DataFrame()
    folder = "data/arcgis/"
    for dirname, _, filenames in os.walk(folder):
        for filename in filenames:
            if filename.rsplit(".", 1)[1] == "csv":
                source_arcgis = pd.concat(
                    [
                        source_arcgis,
                        pd.read_csv(
                            folder + r"/" + filename, parse_dates=["DateCreated","DateUpdated"]
                        ),
                    ]
                )
    source_arcgis["Source"] = "arcgis API"

    ### From usmart api
    source_usmart = pd.DataFrame()
    folder = "data/USMART/"
    for dirname, _, filenames in os.walk(folder):
        for filename in filenames:
            if filename.rsplit(".", 1)[1] == "csv":
                source_usmart = pd.concat(
                    [
                        source_usmart,
                        pd.read_csv(
                            folder + r"/" + filename, parse_dates=["DateCreated","DateUpdated"]
                        ),
                    ]
                )
    source_usmart["Source"] = "USMART API"
    source_usmart["DateUpdated"] = source_usmart["DateUpdated"].dt.tz_localize(None)
    source_usmart["DateCreated"] = source_usmart["DateCreated"].dt.tz_localize(None)

    ## From DCAT
    source_dcat = pd.DataFrame()
    folder = "data/dcat/"
    for dirname, _, filenames in os.walk(folder):
        for filename in filenames:
            if filename.rsplit(".", 1)[1] == "csv":
                source_dcat = pd.concat(
                    [
                        source_dcat,
                        pd.read_csv(
                            folder + r"/" + filename, parse_dates=["DateCreated","DateUpdated"]
                        ),
                    ]
                )
    source_dcat["DateUpdated"] =  source_dcat["DateUpdated"].dt.tz_localize(None)
    #source_dcat["DateCreated"] = source_dcat["DateCreated"].dt.tz_localize(None) ### DateCreated currently not picked up in dcat so all are NULL
    source_dcat["Source"] = "DCAT feed"

    ## From web scraped results
    source_scraped = pd.DataFrame()
    folder = "data/scraped-results/"
    for dirname, _, filenames in os.walk(folder):
        for filename in filenames:
            if filename.rsplit(".", 1)[1] == "csv":
                source_scraped = pd.concat(
                    [
                        source_scraped,
                        pd.read_csv(
                            folder + r"/" + filename, parse_dates=["DateCreated","DateUpdated"]
                        ),
                    ]
                )
    source_scraped["Source"] = "Web Scraped"

    ### Combine all data into single table
    data = pd.concat(
        [
            source_ckan,
            source_arcgis,
            source_usmart,
            source_scotgov,
            source_dcat,
            source_scraped,
        ]
    )
    data = data.reset_index(drop=True)

    ### Saves copy of data without cleaning - for analysis purposes
    data.to_csv("data/merged_output_untidy.csv", index=False)

    ### clean data
    data = clean_data(data)

    ### Output cleaned data to csv
    data.to_csv("data/merged_output.csv", index=False)

    return data


def clean_data(dataframe):
    """cleans data in a dataframe

    Args:
        dataframe (pd.dataframe): the name of the dataframe of data to clean

    Returns:
        dataframe: dataframe of cleaned data
    """
    ### to avoid confusion and avoid re-naming everything...
    data = dataframe

    ### Renaming entries to match
    owner_renames = {
        "Aberdeen": "Aberdeen City Council",
        "Dundee": "Dundee City Council",
        "Perth": "Perth and Kinross Council",
        "Stirling": "Stirling Council",
        "Angus": "Angus Council",
        "open.data@southayrshire": "South Ayrshire Council",
        "SEPA": "Scottish Environment Protection Agency",
        "South Ayrshire": "South Ayrshire Council",
        "East Ayrshire": "East Ayrshire Council",
        "Highland Council GIS Organisation": "Highland Council",
        "Scottish.Forestry": "Scottish Forestry",
        "Na h-Eileanan an Iar": "Comhairle nan Eilean Siar",
    }
    data["Owner"] = data["Owner"].replace(owner_renames)
    ### Format dates as datetime type
    data["DateCreated"] = pd.to_datetime(
        data["DateCreated"], format="%Y-%m-%d", errors="coerce", utc=True
    ).dt.date
    data["DateUpdated"] = pd.to_datetime(
        data["DateUpdated"], format="%Y-%m-%d", errors="coerce", utc=True
    ).dt.date
    ### Inconsistencies in casing for FileType
    data["FileType"] = data["FileType"].str.upper()
    ### Creating a dummy column
    data["AssetStatus"] = None

    ### Cleaning dataset categories
    def tidy_categories(categories_string):
        """tidies the categories: removes commas, strips whitespace, converts all to lower and strips any trailing ";"

        Args:
            categories_string (string): the dataset categories as a string
        """
        tidied_string = str(categories_string).replace(",", ";")
        tidied_list = [
            cat.lower().strip() for cat in tidied_string.split(";") if cat != ""
        ]
        tidied_string = ";".join(str(cat) for cat in tidied_list if str(cat) != "nan")
        if len(tidied_string) > 0:
            if tidied_string[-1] == ";":
                tidied_string = tidied_string[:-1]
        return tidied_string

    ### Combining dataset categories
    def combine_categories(dataset_row):
        """Combine OriginalTags and ManualTags to get all tags

        Args:
            dataset_row (dataframe): one row of the dataset set
        """
        combined_tags = []
        if str(dataset_row["OriginalTags"]) != "nan":
            combined_tags = combined_tags + str(dataset_row["OriginalTags"]).split(";")
        if str(dataset_row["ManualTags"]) != "nan":
            combined_tags = combined_tags + str(dataset_row["ManualTags"]).split(";")

        combined_tags = ";".join(str(cat) for cat in set(combined_tags))
        return combined_tags

    data["OriginalTags"] = data["OriginalTags"].apply(tidy_categories)
    data["ManualTags"] = data["ManualTags"].apply(tidy_categories)
    data["CombinedTags"] = data.apply(lambda x: combine_categories(x), axis=1)

    ### Creating new dataset categories for ODS
    def assign_ODScategories(categories_string):
        """Assigns one of ODS' 13 categories, or 'Uncategorised' if none.

        Args:
            categories_string (string): the dataset categories as a string
        """
        combined_tags = categories_string.split(";")

        ### Set association between dataset tag and ODS category
        ods_categories = {
            "Arts / Culture / History": [
                "arts",
                "culture",
                "history",
                "military",
                "art gallery",
                "design",
                "fashion",
                "museum",
                "historic centre",
                "conservation",
                "archaeology",
                "events",
                "theatre",
            ],
            "Budget / Finance": [
                "tenders",
                "contracts",
                "lgcs finance",
                "budget",
                "finance",
                "payment",
                "grants",
                "financial year",
                "council tax",
            ],
            "Business and Economy": [
                "business and economy",
                "business",
                "business and trade",
                "economic information",
                "economic development",
                "business grants",
                "business awards",
                "health and safety",
                "trading standards",
                "food safety",
                "business rates",
                "commercial land and property" "commercial waste",
                "pollution",
                "farming",
                "forestry",
                "crofting",
                "countryside",
                "farming",
                "emergency planning",
                "health and safety",
                "trading standards",
                "health and safety at work",
                "regeneration",
                "shopping",
                "shopping centres",
                "markets",
                "tenders",
                "contracts",
                "city centre management",
                "town centre management",
                "economy",
                "economic",
                "economic activity",
                "economic development",
                "deprivation",
                "scottish index of multiple deprivation",
                "simd",
                "business",
                "estimated population",
                "population",
                "labour force",
            ],
            "Council and Government": [
                "council buildings",
                "community development",
                "council and government",
                "council",
                "councils",
                "council tax",
                "benefits",
                "council grants",
                "grants",
                "council departments",
                "data protection",
                "FOI",
                "freedom of information",
                "council housing",
                "politicians",
                "MPs",
                "MSPs",
                "councillors",
                "elected members",
                "wards",
                "constituencies",
                "boundaries",
                "council minutes",
                "council agendas",
                "council plans",
                "council policies",
            ],
            "Education": [
                "primary schools",
                "lgcs education & skills",
                "education",
                "eductional",
                "library",
                "school meals",
                "schools",
                "school",
                "nurseries",
                "playgroups",
            ],
            "Elections / Politics": [
                "community councils",
                "political",
                "polling places",
                "elections",
                "politics",
                "elecorate",
                "election",
                "electoral",
                "electorate",
                "local authority",
                "council area",
                "democracy",
                "polling",
                "lgcs democracy",
                "democracy and governance",
                "local government",
                "councillor",
                "councillors",
                "community council",
            ],
            "Food and Environment": [
                "food",
                "school meals",
                "allotment",
                "public toilets",
                "air",
                "tree",
                "vacant and derelict land supply",
                "landscape",
                "nature",
                "rights of way",
                "tree preservation order",
                "preservation",
                "land",
                "contaminated",
                "green",
                "belt",
                "employment land audit",
                "environment",
                "forest woodland strategy",
                "waste",
                "recycling",
                "lgcs waste management",
                "water-network",
                "grafitti",
                "street occupations",
                "regeneration",
                "vandalism",
                "street cleansing",
                "litter",
                "toilets",
                "drains",
                "flytipping",
                "flyposting",
                "pollution",
                "air quality",
                "household waste",
                "commercial waste",
            ],
            "Health and Social Care": [
                "public toilets",
                "contraception",
                "implant",
                "cervical",
                "iud",
                "ius",
                "pis",
                "prescribing",
                "elderly",
                "screening",
                "screening programme",
                "cancer",
                "breast feeding",
                "defibrillators",
                "wards",
                "alcohol and drug partnership",
                "care homes",
                "waiting times",
                "drugs",
                "substance use",
                "pregnancy",
                "induced abortion",
                "therapeutic abortion",
                "termination",
                "abortion",
                "co-dependency",
                "sexual health",
                "outpatient",
                "waiting list",
                "stage of treatment",
                "daycase",
                "inpatient",
                "alcohol",
                "waiting time",
                "treatment",
                "community wellbeing and social environment",
                "health",
                "human services",
                "covid-19",
                "covid",
                "hospital",
                "health board",
                "health and social care partnership",
                "medicine",
                "health and social care",
                "health and fitness",
                "nhs24",
                "hospital admissions",
                "hospital mortality",
                "mental health",
                "pharmacy",
                "GP",
                "surgery",
                "fostering",
                "adoption",
                "social work",
                "asylum",
                "immigration",
                "citizenship",
                "carers",
            ],
            "Housing and Estates": [
                "buildings",
                "housing data supply 2020",
                "multiple occupation",
                "housing",
                "sheltered housing",
                "adaptations",
                "repairs",
                "council housing",
                "landlord",
                "landlord registration",
                "rent arrears",
                "parking",
                "garages",
                "homelessness",
                "temporary accommodation",
                "rent",
                "tenancy",
                "housing advice",
                "housing associations",
                "housing advice",
                "housing repairs",
                "lettings",
                "real estate",
                "land records",
                "land-cover",
                "woodland",
                "dwellings",
                "burial grounds",
                "cemeteries",
                "property",
                "vacant and derelict land",
                "scottish vacant and derelict land",
                "allotment",
            ],
            "Law and Licensing": [
                "law",
                "licensing",
                "regulation",
                "regulations",
                "licence",
                "licenses",
                "permit",
                "permits",
                "police",
                "court",
                "courts",
                "tribunal",
                "tribunals",
            ],
            "Parks / Recreation": [
                "parks",
                "recreation",
                "woodland",
                "parks and open spaces",
            ],
            "Planning and Development": [
                "buildings",
                "vacant and derelict land supply",
                "core paths. adopted",
                "employment land audit",
                "built environment",
                "planning",
                "zoning",
                "council area",
                "address",
                "addresses",
                "city development plan",
                "boundaries",
                "post-code",
                "dwellings",
                "planning permission",
                "postcode-units",
                "housing",
                "property",
                "building control",
                "conservation",
            ],
            "Public Safety": [
                "emergency planning",
                "public safety",
                "crime and justice",
                "lgcs community safety",
                "street lighting",
                "community safety",
                "cctv",
                "road safety",
            ],
            "Sport and Leisure": [
                "sport",
                "sports",
                "sports facilities",
                " sports activities",
                "countryside",
                "wildlife",
                "leisure",
                "leisure clubs",
                "clubs",
                "groups",
                "societies",
                "libraries",
                "archives",
                "local history",
                "heritage",
                "museums",
                "galleries",
                "parks",
                "gardens",
                "open spaces",
                "sports",
                "sports clubs",
                "leisure centres",
            ],
            "Tourism": [
                "public toilets",
                "tourism",
                "tourist",
                "attractions",
                "accomodation",
                "historic buildings",
                "tourist routes",
                "cafes",
                "restaurants",
                "hotels",
                "hotel",
            ],
            "Transportation": [
                "core paths. adopted",
                "lgcs transport infrastructure",
                "transportation",
                "mobility",
                "pedestrian",
                "walking",
                "walk",
                "cycle",
                "cycling",
                "parking",
                "car",
                "bus",
                "tram",
                "train",
                "taxi",
                "transport",
                "electric vehicle",
                "electric vehicle charging points",
                "transport / mobility",
                "active travel",
                "road safety",
                "roads",
                "community transport",
                "road works",
                "road closures",
                "speed limits",
                "port",
                "harbour",
            ],
        }

        ### Return ODS if tag is a match
        applied_category = []
        for tag in combined_tags:
            for cat in ods_categories:
                if tag in ods_categories[cat]:
                    applied_category = applied_category + [cat]

        ### If no match, assign "Uncategorised". Tidy list of ODS categories into string.
        if len(applied_category) == 0:
            applied_category = ["Uncategorised"]

        applied_category = ";".join(str(cat) for cat in set(applied_category))
        applied_category

        return applied_category

    ### Apply ODS categorisation
    data["ODSCategories"] = data["CombinedTags"].apply(assign_ODScategories)


    ### Tidy licence names
    def tidy_licence(licence_name):
        """Temporary licence conversion to match export2jkan -- FOR ANALYTICS ONLY, will discard in 2022Q2 Milestone
        Returns:
            string: a tidied licence name
        """
        known_licences = {
            "https://creativecommons.org/licenses/by-sa/3.0/": "Creative Commons Attribution Share-Alike 3.0",
            "https://creativecommons.org/licenses/by/4.0/legalcode": "Creative Commons Attribution 4.0 International",
            "https://creativecommons.org/licenses/by/4.0": "Creative Commons Attribution 4.0 International",
            "Creative Commons Attribution 4.0": "Creative Commons Attribution 4.0 International",
            "https://creativecommons.org/share-your-work/public-domain/cc0": "Creative Commons CC0",
            "https://rightsstatements.org/page/NoC-NC/1.0/": "Non-Commercial Use Only",
            "https://opendatacommons.org/licenses/odbl/1-0/": "Open Data Commons Open Database License 1.0",
            "Open Data Commons Open Database License 1.0": "Open Data Commons Open Database License 1.0",
            "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/2/": "Open Government Licence v2.0",
            "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/": "Open Government Licence v3.0",
            "Open Government Licence 3.0 (United Kingdom)": "Open Government Licence v3.0",
            "UK Open Government Licence (OGL)": "Open Government Licence v3.0",
            "Open Government": "Open Government Licence v3.0",
            "uk-ogl": "Open Government Licence v3.0",
            "OGL3": "Open Government Licence v3.0",
            "https://rightsstatements.org/vocab/NKC/1.0/": "No Known Copyright",
            "https://creativecommons.org/publicdomain/mark/1.0/": "Public Domain",
            "Other (Public Domain)": "Public Domain",
            "Public Domain": "Public Domain",
            "Public Sector End User Licence (Scotland)": "Public Sector End User Licence (Scotland)",
        }

        for key in known_licences.keys():
            if str(licence_name).lower().strip(" /") == key.lower().strip(" /"):
                return known_licences[key]

        if str(licence_name) == "nan":
                tidied_licence = "No licence"
        else:
                tidied_licence = "Custom licence: " + str(licence_name)
        return tidied_licence

    data["License"] = data["License"].apply(tidy_licence)


    def tidy_file_type(file_type):
        """ Temporary data type conversion
        Args:
            file_type (str): the data type name
        Returns:
            tidied_file_type (str): a tidied data type name
        """
        file_types_to_tidy = {
            "application/x-7z-compressed": "7-Zip compressed file",
            "ArcGIS GeoServices REST API": "ARCGIS GEOSERVICE",
            "Esri REST": "ARCGIS GEOSERVICE",
            "Atom Feed": "ATOM FEED",
            "htm": "HTML",
            "ics": "iCalendar",
            "jpeg": "Image",
            "vnd.openxmlformats-officedocument.spreadsheetml.sheet": "MS EXCEL",
            "vnd.ms-excel": "MS EXCEL",
            "xls": "MS EXCEL",
            "xlsx": "MS EXCEL",
            "doc": "MS Word",
            "docx": "MS Word",
            "QGIS": "QGIS Shapefile",
            "text": "TXT",
            "web": "URL",
            "UK/DATA/#TABGB1900": "URL",
            "UK/ROY/GAZETTEER/#DOWNLOAD": "URL",
            "Web Mapping Application": "WEB MAP",
            "mets": "XML",
            "alto": "XML",
        }
        tidied_data_type = "NULL"

        for key in file_types_to_tidy.keys():
            if str(file_type).lower().strip(". /") == key.lower().strip(". /"):
                tidied_file_type = file_types_to_tidy[key]
                return tidied_file_type

        if (
            str(file_type) == "nan"
            or str(file_type) == ""
        ):
            tidied_file_type = "No file type"
        else:
            # print("file type: ", file_type)
            tidied_file_type = str(file_type).strip(". /").upper()

        return tidied_file_type

    ### Inconsistencies in casing for FileType
    data['FileType'] = data['FileType'].apply(tidy_file_type)

    return data


if __name__ == "__main__":
    merge_data()

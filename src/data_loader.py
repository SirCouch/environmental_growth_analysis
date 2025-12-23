
import requests
import pandas as pd
import time

INDICATORS = {
    'NY.GDP.PCAP.KD': 'GDP_per_capita',
    # 'EN.ATM.CO2E.PC': 'CO2_per_capita', # Using OWID
    'SE.TER.ENRR': 'Education_Tertiary',
    'RL.EST': 'Rule_of_Law' # WGI
}

def get_countries_by_income():
    print("Fetching country list...")
    # Fetch country info
    url = "http://api.worldbank.org/v2/country?format=json&per_page=300"
    resp = requests.get(url)
    data = resp.json()
    
    if len(data) < 2:
        print("Failed to fetch countries")
        return [], []
        
    countries = data[1]
    
    hic = []
    lmic = []
    
    for c in countries:
        if c['region']['value'] == 'Aggregates':
            continue
        
        inc = c['incomeLevel']['id']
        if inc == 'HIC':
            hic.append(c['id'])
        elif inc in ['LIC', 'LMC', 'UMC']:
            lmic.append(c['id'])
            
    print(f"Found {len(hic)} HIC and {len(lmic)} LMIC.")
    # Return top 20 of each
    return hic[:20], lmic[:20]

def fetch_indicator(country_codes, indicator):
    # Join countries with ;
    # API limit is usually around 10-20 countries per call for standard users?
    # Or we can use 'all' and filter? But filtering is slow.
    # We will fetch for specific countries in chunks.
    
    # Chunk size 10
    chunk_size = 10
    all_rows = []
    
    # Need to handle source for RL.EST? usually API finds it if unique, or use source param
    # RL.EST is in source 3 (WGI).
    # We can try adding &source=3 for that indicator, or just let API route it.
    
    url_base = f"http://api.worldbank.org/v2/country/"
    
    for i in range(0, len(country_codes), chunk_size):
        chunk = country_codes[i:i+chunk_size]
        cc_str = ";".join(chunk)
        
        url = f"{url_base}{cc_str}/indicator/{indicator}?format=json&date=1990:2020&per_page=5000"
        # For Rule of Law, add source=3 just in case?
        if indicator == 'RL.EST':
            url += "&source=3"
            
        print(f"Fetching {indicator} for chunk {chunk}...")
        try:
            r = requests.get(url)
            if r.status_code != 200:
                print(f"Error {r.status_code}")
                continue
            
            content = r.json()
            if len(content) < 2:
                # No data
                continue
            
            data_list = content[1]
            if data_list is None:
                continue
                
            for entry in data_list:
                val = entry['value']
                date = entry['date']
                # Use ISO3 code for compatibility with OWID
                # country = entry['country']['id'] # This is usually ISO2 (e.g. US)
                country = entry.get('countryiso3code', entry['country']['id']) # Fallback just in case
                
                if val is not None:
                    all_rows.append({
                        'country': country,
                        'year': int(date),
                        indicator: val
                    })
        except Exception as e:
            print(f"Exception: {e}")
            
        time.sleep(0.5) # Be nice to API
        
    return pd.DataFrame(all_rows)

def process_data():
    hic, lmic = get_countries_by_income()
    all_countries = hic + lmic
    print(f"Selected {len(all_countries)} target countries.")
    
    dfs = []
    
    # Initialize base DF with countries/years?
    # Better: fetch each indicator and merge.
    
    merged_df = None
    
    for ind_code, ind_name in INDICATORS.items():
        df = fetch_indicator(all_countries, ind_code)
        if df.empty:
            print(f"Warning: No data for {ind_name}")
            continue
            
        # Rename value column
        df = df.rename(columns={ind_code: ind_name})
        
        if merged_df is None:
            merged_df = df
        else:
            merged_df = pd.merge(merged_df, df, on=['country', 'year'], how='outer')
            
    

    # Fetch OWID CO2
    print("Fetching CO2 data from Our World In Data...")
    try:
        owid_url = "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"
        df_owid = pd.read_csv(owid_url, usecols=['iso_code', 'year', 'co2_per_capita'])
        df_owid = df_owid.rename(columns={'iso_code': 'country', 'co2_per_capita': 'CO2_per_capita'})
        
        # Filter for our countries and years
        print(f"OWID Rows raw: {len(df_owid)}")
        df_owid = df_owid[df_owid['country'].isin(all_countries)]
        print(f"OWID Rows filtered by country: {len(df_owid)}")
        df_owid = df_owid[(df_owid['year'] >= 1990) & (df_owid['year'] <= 2020)]
        print(f"OWID Rows filtered by year: {len(df_owid)}")
        
        if not df_owid.empty:
            print("OWID Head:")
            print(df_owid.head())
            
        if merged_df is not None:
             # Check types
            print(f"Merged Year Type: {merged_df['year'].dtype}")
            print(f"OWID Year Type: {df_owid['year'].dtype}")
            
            merged_df = pd.merge(merged_df, df_owid, on=['country', 'year'], how='left')
            print("Merged OWID CO2 data.")
            print(f"CO2 non-null: {merged_df['CO2_per_capita'].count()}")
        else:
            merged_df = df_owid
            
    except Exception as e:
        print(f"Failed to fetch OWID data: {e}")

    # Add income group
    def get_group(c):
        if c in hic: return 'High Income'
        if c in lmic: return 'Low-Middle Income'
        return 'Unknown'
        
    if merged_df is not None:
        merged_df['Income_Group'] = merged_df['country'].apply(get_group)
        print("Data compilation complete.")
        return merged_df
    else:
        return pd.DataFrame()

if __name__ == "__main__":
    df = process_data()
    print(df.head())
    print(df.info())
    df.to_csv("environmental_data.csv", index=False)

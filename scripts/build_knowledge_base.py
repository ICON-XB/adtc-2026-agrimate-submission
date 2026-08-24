"""
AgriMate Knowledge Base Builder
Scrapes FAO documents and generates Lockhart & Wiseman chapter summaries
for the offline RAG database.
"""
import os
import time
import urllib.request
import re

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "knowledge")

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def fetch_url(url):
    """Fetch a URL and return the text content, stripping HTML tags."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        # Strip HTML tags crudely
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    except Exception as e:
        print(f"  [SKIP] {url}: {e}")
        return None

def scrape_fao_documents():
    """Scrape the two FAO documents and their chapter sub-pages."""
    fao_dir = os.path.join(KNOWLEDGE_DIR, "fao_documents")
    ensure_dir(fao_dir)

    documents = [
        {
            "name": "fao_committee_agriculture",
            "base": "https://www.fao.org/4/y8704e/y8704e",
            "chapters": ["", "01", "02", "03", "04", "05", "06", "07", "08", "09", "0a", "0b"],
            "suffix": ".htm",
        },
        {
            "name": "fao_mixed_crop_livestock",
            "base": "https://www.fao.org/4/y0501e/y0501e",
            "chapters": ["00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "0a", "0b", "0c", "0d", "0e", "0f"],
            "suffix": ".htm",
        },
    ]

    for doc in documents:
        print(f"\n--- Scraping: {doc['name']} ---")
        for ch in doc["chapters"]:
            url = f"{doc['base']}{ch}{doc['suffix']}"
            print(f"  Fetching {url}...")
            content = fetch_url(url)
            if content and len(content) > 200:
                label = f"ch{ch}" if ch else "index"
                filepath = os.path.join(fao_dir, f"{doc['name']}_{label}.md")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f"# {doc['name']} - {label}\n\n")
                    f.write(f"Source: {url}\n\n")
                    f.write(content)
                print(f"  [OK] Saved {filepath}")
            else:
                print(f"  [SKIP] No useful content")
            time.sleep(0.5)

def generate_lockhart_wiseman():
    """
    Generate comprehensive chapter summaries for Lockhart & Wiseman's
    Crop Husbandry 10th Edition. Since the textbook is copyrighted,
    we generate detailed educational summaries of each chapter topic
    using publicly available agricultural knowledge.
    """
    lw_dir = os.path.join(KNOWLEDGE_DIR, "lockhart_wiseman")
    ensure_dir(lw_dir)

    chapters = {
        "ch01_plants": """# Chapter 1: Plants

## Plant Biology Fundamentals for Crop Production

Plants are the foundation of all agriculture. Understanding plant structure and function is essential for effective crop management.

### Plant Structure
- Root systems: Fibrous roots (grasses, cereals) vs taproot systems (carrots, sugar beet). Root depth determines drought tolerance and nutrient access.
- Stems: Support the plant and transport water and nutrients. Stem strength is critical for lodging resistance in cereals.
- Leaves: Primary site of photosynthesis. Leaf area index (LAI) determines how efficiently a crop intercepts sunlight.
- Flowers and seeds: Reproductive structures. Understanding pollination (self vs cross) is key to plant breeding and seed production.

### Photosynthesis
- C3 plants (wheat, barley, rice): Less efficient in hot conditions, photorespiration reduces yield at high temperatures.
- C4 plants (maize, sorghum, sugarcane): More efficient water use and CO2 fixation in tropical/subtropical climates.
- Light interception: Crops achieve maximum growth when leaf canopy covers 85-95% of the ground.

### Plant Growth Stages
- Germination: Requires moisture, warmth (soil temperature >5C for most temperate crops), and oxygen.
- Vegetative growth: Tillering in cereals, leaf expansion, root development.
- Reproductive growth: Flowering, grain fill, fruit development.
- Senescence: Natural aging, nutrient remobilization to grain/seed.

### Crop Growth Requirements
- Temperature: Each crop has a base temperature below which growth stops. Accumulated heat units (growing degree days) determine development rate.
- Water: Most crops need 400-600mm of water during the growing season. Water stress during flowering causes the greatest yield loss.
- Nutrients: Nitrogen drives vegetative growth; phosphorus supports root development and energy transfer; potassium regulates water balance and disease resistance.

### Relevance to African Agriculture
In sub-Saharan Africa, understanding C4 photosynthesis is particularly important as maize, sorghum, and millet are staple crops well-adapted to high temperatures. Smallholder farmers benefit from knowledge of critical growth stages to time irrigation and fertilizer applications.""",

        "ch02_climate_weather": """# Chapter 2: Climate and Weather

## Impact of Climate and Weather on Crop Production

Weather is the single largest uncontrollable factor affecting crop yields worldwide.

### Key Climate Factors
- Rainfall: Distribution matters more than total amount. Crops need rain at critical stages (germination, flowering). Prolonged dry spells during grain fill can halve yields.
- Temperature: Determines growing season length. Frost kills sensitive crops. Heat stress above 35C damages pollen viability in many crops.
- Solar radiation: Drives photosynthesis. Cloud cover reduces potential yield. Tropical regions receive more consistent radiation year-round.
- Wind: Causes lodging in tall crops, increases evapotranspiration, and can spread diseases. Windbreaks reduce crop damage by 20-30%.
- Humidity: High humidity promotes fungal diseases (rust, blight). Low humidity increases water stress.

### Climate Zones and Crop Suitability
- Tropical: Year-round growing, multiple cropping possible. Crops: rice, cassava, yams, plantain, cocoa, oil palm.
- Semi-arid: Short rainy season, drought-tolerant crops essential. Crops: sorghum, millet, cowpea, groundnut.
- Mediterranean: Hot dry summers, cool wet winters. Crops: wheat, barley, olives, citrus.
- Temperate: Distinct seasons with cold winters. Crops: wheat, barley, oats, potatoes, sugar beet.

### Climate Change Impacts on African Agriculture
- Shifting rainfall patterns: West Africa's growing season is shortening by 5-10 days per decade in some areas.
- Rising temperatures: Maize yields in sub-Saharan Africa could decline 20-30% by 2050 without adaptation.
- Increased frequency of extreme events: Droughts, floods, and heatwaves are becoming more common.
- Adaptation strategies: Drought-tolerant varieties, conservation agriculture, diversified cropping systems, improved water harvesting.""",

        "ch03_soil_health": """# Chapter 3: Soil Health and Management

## Soil Science for Sustainable Crop Production

Healthy soil is the foundation of productive farming. Soil degradation is one of Africa's biggest agricultural challenges.

### Soil Composition
- Mineral particles: Sand (coarse, drains quickly), silt (medium), clay (fine, holds water and nutrients).
- Organic matter: Decomposed plant and animal material. Critical for soil structure, water retention, and nutrient cycling. Aim for >2% organic matter.
- Water: Held in pore spaces. Field capacity is the maximum water a soil holds after drainage. Wilting point is when plants can no longer extract water.
- Air: Root respiration requires oxygen. Compacted or waterlogged soils restrict root growth.

### Soil Types Common in Africa
- Ferralsols: Deeply weathered, acidic soils common in tropical Africa. Low fertility, require liming and phosphorus.
- Vertisols: Heavy clay soils that crack when dry. Found in Ethiopia, Sudan, central Africa. Difficult to work but potentially fertile.
- Arenosols: Sandy soils with very low water and nutrient holding capacity. Common in the Sahel and Kalahari.
- Andosols: Volcanic soils in East Africa (Kenya highlands, Ethiopian highlands). Highly fertile but prone to phosphorus fixation.

### Soil Management Practices
- Tillage: Conventional (plough, harrow) vs minimum tillage vs no-till. Conservation tillage reduces erosion by 50-90%.
- Cover cropping: Growing crops like mucuna, cowpea, or vetch between main crops to protect soil and fix nitrogen.
- Mulching: Surface application of crop residues reduces evaporation, moderates soil temperature, and builds organic matter.
- Crop rotation: Alternating crop families breaks disease and pest cycles. Including legumes adds 40-80 kg N/ha through biological nitrogen fixation.
- Composting: Converting farm waste into valuable soil amendment. Well-made compost provides nutrients and improves soil structure.

### Soil Erosion Prevention
- Water erosion: Contour ploughing, terracing, grass strips, and maintaining ground cover.
- Wind erosion: Windbreaks, maintaining crop residues, and avoiding bare soil during dry windy periods.
- In Africa, soil erosion causes estimated yield losses of 2-40% depending on severity.""",

        "ch04_fertilisers_manures": """# Chapter 4: Fertilisers and Manures

## Nutrient Management for Crop Production

Adequate nutrition is essential for achieving crop yield potential. Both mineral fertilisers and organic manures play important roles.

### Essential Plant Nutrients
- Macronutrients (needed in large amounts):
  - Nitrogen (N): Required for leaf growth, protein synthesis. Deficiency shows as yellowing of older leaves.
  - Phosphorus (P): Root development, energy transfer, flowering. Deficiency shows as purple/dark green leaves, stunted growth.
  - Potassium (K): Water regulation, disease resistance, grain quality. Deficiency shows as scorching of leaf edges.
- Secondary nutrients: Calcium, magnesium, sulphur.
- Micronutrients: Iron, zinc, manganese, boron, copper, molybdenum. Zinc deficiency is widespread in African soils and causes stunted maize growth.

### Fertiliser Types
- Urea (46% N): Most concentrated nitrogen fertiliser. Apply at tillering and stem elongation in cereals.
- DAP (18% N, 46% P2O5): Commonly used starter fertiliser in Africa. Apply at planting.
- NPK compounds (e.g., 15-15-15): Balanced nutrition. Good for general use but may not match specific crop needs.
- CAN (27% N): Calcium ammonium nitrate. Less volatile than urea, good for top-dressing.

### Organic Nutrient Sources
- Farmyard manure (FYM): Cattle manure provides approximately 5 kg N, 3 kg P, 8 kg K per tonne. Apply 10-20 t/ha.
- Compost: Nutrient content varies. Valuable for improving soil structure and water-holding capacity.
- Green manures: Leguminous cover crops (Mucuna, Crotalaria, Tephrosia) can fix 60-200 kg N/ha.
- Biochar: Charcoal added to soil improves nutrient retention and carbon sequestration. Traditional practice in parts of West Africa.

### Integrated Soil Fertility Management (ISFM)
This approach, widely promoted across Africa, combines:
- Mineral fertilisers at recommended rates
- Organic inputs (manure, compost, crop residues)
- Improved germplasm (responsive varieties)
- Adaptation to local conditions
- ISFM can double or triple yields compared to either organic or mineral inputs alone.""",

        "ch05_weeds": """# Chapter 5: Weeds

## Weed Biology and Management in Crop Production

Weeds compete with crops for light, water, and nutrients. Uncontrolled weeds can reduce yields by 50-100%.

### Common Weeds in African Agriculture
- Striga (witchweed): Parasitic weed that attacks cereal roots (maize, sorghum, millet). Causes devastating losses across sub-Saharan Africa. Infected fields can lose 40-100% of yield.
- Imperata cylindrica (cogon grass): Aggressive perennial grass that invades farmland in West and Central Africa.
- Cyperus rotundus (purple nutsedge): One of the world's worst weeds. Reproduces through tubers making it very difficult to control.
- Ageratum conyzoides: Common broadleaf weed in tropical croplands.

### Weed Control Methods
- Cultural control: Timely planting, adequate crop density, competitive varieties, mulching, crop rotation.
- Mechanical control: Hand weeding (most common in smallholder Africa), hoeing, inter-row cultivation.
- Chemical control: Herbicides classified as pre-emergence (applied before weed germination) or post-emergence (applied to growing weeds). Glyphosate, atrazine, 2,4-D are commonly used.
- Biological control: Using natural enemies. Some success with Fusarium oxysporum against Striga.
- Integrated Weed Management (IWM): Combining multiple methods for sustainable weed control.

### Striga Management
Given Striga's devastating impact across Africa, specific strategies include:
- Resistant/tolerant varieties of maize and sorghum
- Push-pull technology: Intercropping with Desmodium (silverleaf) repels Striga while Napier grass on borders attracts stem borers away from the crop
- Soil fertility improvement: Well-fertilised crops are more resistant
- Crop rotation with trap crops (soybeans, groundnuts) that stimulate Striga germination but are not parasitised""",

        "ch06_diseases": """# Chapter 6: Diseases

## Crop and Livestock Disease Management

Plant diseases cause estimated losses of 10-30% of global food production annually.

### Major Crop Diseases in Africa
- Maize lethal necrosis (MLN): Viral disease devastating maize production in East Africa. Transmitted by thrips and beetles. No cure; management through resistant varieties and vector control.
- Wheat stem rust (Ug99): Originated in Uganda in 1999. Threatens wheat production across Africa and beyond. Race-specific resistance genes are overcome; durable resistance needed.
- Cassava mosaic disease (CMD): Viral, transmitted by whitefly. Major threat to food security in Central and West Africa. Resistant varieties available.
- Banana Xanthomonas wilt (BXW): Bacterial disease destroying banana plantations in East and Central Africa. Management through removal of male buds, use of clean planting material.
- Late blight of potato: Caused by Phytophthora infestans. Particularly severe in highland areas of East Africa.

### Livestock Diseases Common in Africa
- Lumpy Skin Disease (LSD): Caused by Lumpy Skin Disease Virus (LSDV). Transmitted by blood-feeding insects (mosquitoes, ticks, biting flies). Symptoms include firm, round skin nodules 2-5cm in diameter across the body, fever, reduced milk production, and weight loss. Prevention: vaccination with live attenuated vaccines. Treatment: antibiotics for secondary infections, anti-inflammatory drugs. Isolate affected animals immediately.
- East Coast Fever (ECF): Tick-borne disease caused by Theileria parva. Kills up to 1 million cattle annually in East Africa.
- Foot-and-mouth disease (FMD): Highly contagious viral disease. Major barrier to livestock trade from Africa.
- Newcastle disease: Kills up to 80% of unvaccinated village poultry flocks. Thermostable vaccines (I-2) available for village use.
- African swine fever (ASF): Highly lethal viral disease of pigs. No vaccine available. Control through biosecurity and movement restrictions.

### Disease Management Principles
- Prevention: Use resistant varieties, certified disease-free seed/planting material, good hygiene.
- Cultural control: Crop rotation, removal of crop debris, proper spacing for air circulation.
- Chemical control: Fungicides (protectant and systemic), bactericides. Must be applied preventively or at early infection.
- Biological control: Trichoderma species as biocontrol agents against soil-borne diseases.
- Integrated Disease Management: Combining genetic resistance with cultural practices and targeted chemical use.""",

        "ch07_pests": """# Chapter 7: Pests

## Insect Pest Management in Agriculture

Insect pests cause 10-20% crop losses in Africa, and up to 40% in storage.

### Major Crop Pests in Africa
- Fall armyworm (Spodoptera frugiperda): Invaded Africa in 2016. Devastating pest of maize, sorghum, and other crops across the continent. Larvae feed on leaves and ears.
- Stem borers (Busseola fusca, Chilo partellus): Major pests of maize and sorghum. Larvae bore into stems causing dead hearts and broken stems.
- Desert locust (Schistocerca gregaria): Periodically forms massive swarms that can destroy entire harvests across the Sahel and East Africa.
- Tsetse fly (Glossina spp.): Transmits trypanosomiasis (sleeping sickness) in cattle. Restricts livestock production across the tsetse belt.
- Fruit flies (Ceratitis spp.): Major pests of mango, citrus, and other fruits. Barrier to export of African fresh produce.

### Pest Control Methods
- Cultural control: Early planting, crop rotation, intercropping, destruction of crop residues harbouring pests.
- Biological control: Using natural enemies. Cotesia flavipes parasitoid wasp released against stem borers. Bt maize provides genetic resistance to stem borers.
- Chemical control: Insecticides should be used judiciously. Resistance development is a major concern. IPM approaches preferred.
- Push-pull technology: Developed by ICIPE in Kenya. Intercrop maize with Desmodium (repels stem borers) and border-plant with Napier grass (attracts and traps borers). Also controls Striga. Adopted by over 250,000 farmers in East Africa.

### Post-Harvest Pest Management
- Larger grain borer (Prostephanus truncatus): Devastating pest of stored maize in Africa.
- Hermetic storage: Using airtight containers (PICS bags, metal silos) suffocates storage pests without chemicals. Reduces losses from 20-30% to under 2%.
- Proper drying: Grain must be dried to below 13% moisture before storage.""",

        "ch08_sustainable_production": """# Chapter 8: Sustainable Crop Production Techniques

## Sustainable Agriculture Practices

Sustainable agriculture meets present food needs without compromising future generations' ability to meet their needs.

### Conservation Agriculture (CA)
Three principles:
1. Minimum soil disturbance (no-till or reduced tillage)
2. Permanent soil cover (mulch, cover crops)
3. Crop rotation and diversification

Benefits: Reduces erosion, improves water infiltration, builds soil organic matter, reduces labour costs.
In Africa: Widely promoted in Southern Africa (Zambia, Zimbabwe, Malawi). Adoption challenges include competing uses for crop residues (livestock feed, fuel).

### Agroforestry
Integrating trees with crops and/or livestock:
- Alley cropping: Rows of nitrogen-fixing trees (Gliricidia, Sesbania, Faidherbia) with crops between. Faidherbia albida is particularly valuable in Africa as it drops its leaves during the rainy season, providing nutrients without shading crops.
- Improved fallows: Planting fast-growing leguminous trees during fallow periods to restore soil fertility.
- Parkland systems: Traditional agroforestry in West Africa with scattered trees (shea, baobab, nere) in croplands.

### Water Harvesting and Irrigation
- Rainwater harvesting: Collecting runoff in ponds, tanks, or underground cisterns for supplementary irrigation.
- Zai pits (Burkina Faso): Small planting pits filled with compost that concentrate water and nutrients around the plant.
- Half-moon terraces: Semi-circular earth bunds that capture runoff on slopes.
- Drip irrigation: Most water-efficient method. Solar-powered drip systems increasingly affordable for African smallholders.

### Integrated Crop-Livestock Systems
- Animals provide manure for crops; crops provide feed for animals.
- In mixed farming systems across Africa, crop residues feed livestock during the dry season while manure maintains soil fertility.
- Dual-purpose crop varieties (e.g., cowpea with good grain and fodder yield) maximise system productivity.""",

        "ch09_precision_agriculture": """# Chapter 9: Precision Crop Production

## Technology-Enabled Agriculture

Precision agriculture uses technology to manage crops at a detailed level, optimising inputs and reducing waste.

### Key Technologies
- GPS guidance: Enables precise field operations, reduces overlaps and gaps in spraying and spreading.
- Variable rate application: Adjusting fertiliser, seed, or pesticide rates across a field based on soil maps or crop sensors.
- Remote sensing: Satellite and drone imagery to monitor crop health, identify stress areas, and estimate yields.
- Soil mapping: Detailed soil sampling and analysis to understand field variability.

### Relevance to Africa
- Mobile phone applications: Africa has high mobile phone penetration. Apps like PlantVillage, iCow, and DigiFarm provide extension advice, market prices, and weather forecasts.
- Drone technology: Increasingly used for crop scouting and targeted spraying in commercial agriculture in South Africa, Kenya, and Nigeria.
- Satellite-based crop monitoring: Services like FEWS NET use remote sensing to predict food security crises across Africa.
- Digital soil mapping: Africa Soil Information Service (AfSIS) provides continent-wide soil data for better fertiliser recommendations.""",

        "ch10_organic_farming": """# Chapter 10: Organic Crop Husbandry

## Organic Agriculture Principles and Practice

Organic farming relies on ecological processes, biodiversity, and locally adapted practices rather than synthetic inputs.

### Principles
- Health: Organic agriculture sustains the health of soil, ecosystem, and people.
- Ecology: Based on living ecological systems and cycles.
- Fairness: Equitable relationships and fair quality of life.
- Care: Precautionary and responsible management.

### Organic Practices
- Soil fertility: Composting, green manures, crop rotation with legumes. No synthetic fertilisers.
- Pest and disease management: Biological control, resistant varieties, cultural practices. No synthetic pesticides.
- Weed management: Mechanical cultivation, mulching, competitive crops. No synthetic herbicides.

### Organic Agriculture in Africa
- Many African smallholders are already de facto organic (using no synthetic inputs) but lack certification.
- Certified organic exports (coffee, cocoa, cotton, vanilla, herbs) earn premium prices.
- Uganda, Tanzania, and Ethiopia lead African organic production.
- Participatory Guarantee Systems (PGS) provide lower-cost certification suitable for local markets.""",

        "ch11_plant_breeding": """# Chapter 11: Principles of Plant Breeding

## Crop Improvement Through Breeding

Plant breeding has dramatically increased crop yields and quality over the past century.

### Breeding Methods
- Mass selection: Selecting the best plants from a population. Simple but effective for improving local varieties.
- Hybridisation: Crossing two parent varieties to combine desirable traits. F1 hybrids show hybrid vigour (heterosis).
- Backcrossing: Incorporating a single trait (e.g., disease resistance) into an established variety.
- Mutation breeding: Using radiation or chemicals to induce useful mutations.

### Modern Breeding Technologies
- Marker-assisted selection (MAS): Using DNA markers linked to desirable genes to speed up selection.
- Genomic selection: Predicting performance from genome-wide marker data.
- Genome editing (CRISPR): Precise modification of specific genes. Potential for rapid development of disease-resistant and climate-adapted crops.

### Seed Systems in Africa
- Formal seed sector: Research institutions (CGIAR centres like IITA, CIMMYT, ICRISAT) breed improved varieties.
- Community seed banks: Farmers save, exchange, and sell locally adapted seeds.
- Challenges: Many African farmers use saved seed (70-80%), limiting adoption of improved varieties. Seed access and affordability remain key constraints.""",

        "ch12_world_agriculture": """# Chapter 12: World Agricultural Systems

## Global and African Agricultural Systems

Agriculture employs more people than any other sector globally, with the highest proportion in Africa.

### African Agricultural Systems
- Smallholder farming: 80% of African farms are under 2 hectares. These farms produce most of the continent's food.
- Pastoral systems: Nomadic and semi-nomadic herding in drylands (Sahel, Horn of Africa, Southern Africa).
- Commercial farming: Large-scale mechanised farming in South Africa, Kenya highlands, and North Africa.
- Plantation agriculture: Export crops (cocoa, coffee, tea, rubber, oil palm) in West and East Africa.
- Urban and peri-urban agriculture: Growing importance for food security in rapidly urbanising Africa.

### Key Challenges for African Agriculture
- Low productivity: Average cereal yields in sub-Saharan Africa are 1.5 t/ha vs 4 t/ha globally.
- Climate change: Shifting rainfall, rising temperatures, more extreme weather events.
- Land degradation: Soil erosion, nutrient depletion, deforestation.
- Limited infrastructure: Poor roads, inadequate storage, unreliable markets.
- Post-harvest losses: 20-40% of harvested food is lost before reaching consumers.

### Opportunities
- Closing the yield gap: African farmers could double or triple yields with existing technologies.
- Value addition: Processing crops locally creates jobs and adds value.
- Digital agriculture: Mobile technology enables access to information, finance, and markets.
- Youth engagement: Africa's young population is an opportunity if agriculture becomes attractive and profitable.""",

        "ch13_cereals": """# Chapter 13: Cereals

## Cereal Crop Production and Management

Cereals are the foundation of food security worldwide and in Africa.

### Major Cereals in Africa
- Maize: Most widely grown cereal in sub-Saharan Africa. Staple food for 300 million Africans. Optimal temperature 20-30C. Requires 500-800mm rainfall.
- Rice: Growing rapidly in West Africa (Nigeria, Guinea, Sierra Leone, Mali). Both upland and lowland (paddy) cultivation.
- Wheat: Grown in North Africa (Egypt, Morocco, Tunisia), Ethiopia, South Africa, Kenya. Prefers cooler temperatures.
- Sorghum: Drought-tolerant, grown extensively in the Sahel, East Africa, and Southern Africa. Tolerates poor soils and high temperatures.
- Millet (pearl millet, finger millet): Most drought-tolerant cereals. Staple in the driest parts of West Africa and India. Can produce grain with as little as 250mm rainfall.
- Teff: Endemic to Ethiopia. Tiny grain, highly nutritious, gluten-free. Growing international demand.

### Cereal Management Principles
- Land preparation: Good seedbed preparation ensures uniform germination and crop establishment.
- Planting date: Critical for matching crop development to rainfall patterns. Late planting reduces yields 1-2% per day of delay.
- Plant population: Optimal density varies by crop and conditions. Maize: 60,000-90,000 plants/ha.
- Fertilisation: Nitrogen is typically the most limiting nutrient. Split applications (at planting and during vegetative growth) improve efficiency.
- Weed control: Critical in the first 3-4 weeks after emergence when competition is most damaging.
- Harvesting: Timing is critical. Delayed harvest increases shattering losses and quality deterioration.""",

        "ch14_oilseeds_pulses": """# Chapter 14: Oilseeds and Pulse Crops

## Oilseed and Pulse Production in Africa

These crops provide essential protein, oil, and income for millions of African farmers.

### Major Oilseed Crops in Africa
- Groundnut (peanut): Major crop in West Africa (Nigeria, Senegal, Mali) and Southern Africa. Provides protein-rich food and cooking oil.
- Soybean: Rapidly expanding in Nigeria, South Africa, Zambia, Malawi. Excellent source of protein and oil.
- Sunflower: Important in Southern Africa (Tanzania, South Africa). Tolerates moderate drought.
- Sesame: Growing export crop in Ethiopia, Sudan, Nigeria, Tanzania. Known as "white gold" for its high value.
- Oil palm: Major plantation crop in West and Central Africa (Nigeria, Ghana, Cameroon, Ivory Coast).

### Major Pulse Crops in Africa
- Cowpea: Most important pulse in West Africa. Extremely drought-tolerant and nitrogen-fixing. Provides both grain and animal fodder.
- Common bean: Staple protein source in East and Southern Africa. Multiple market classes.
- Chickpea: Growing crop in Ethiopia and East Africa. Both desi and kabuli types.
- Pigeon pea: Important in East and Southern Africa (Malawi, Tanzania, Kenya). Perennial growth allows harvest in dry season.
- Lentil: Grown in Ethiopia and North Africa.

### Agronomic Benefits of Legumes
- Biological nitrogen fixation: Legumes fix 40-200 kg N/ha through symbiosis with Rhizobium bacteria.
- Crop rotation: Breaking cereal disease and pest cycles. Cereal yields increase 15-25% when following a legume.
- Soil improvement: Deep roots improve soil structure. Residues add organic matter.
- Nutritional value: High protein content addresses malnutrition in cereal-dependent diets.""",

        "ch15_root_crops": """# Chapter 15: Root Crops

## Root and Tuber Crop Production

Root crops are critical for food security across tropical Africa.

### Major Root Crops in Africa
- Cassava: Most important root crop in Africa. Produces more calories per hectare than any cereal. Extremely drought-tolerant. Can remain in the ground for 2+ years as a food reserve. Challenges: cyanide content in bitter varieties requires processing; cassava mosaic disease.
- Sweet potato: Fast-growing (harvest in 3-5 months). Orange-fleshed varieties provide vitamin A, addressing nutritional deficiencies. Widely grown in East and Southern Africa.
- Yam: Staple in West Africa (Nigeria produces 70% of world's yams). Labour-intensive but high-value crop.
- Potato (Irish): Important in highland areas of East Africa (Kenya, Ethiopia, Rwanda). High-yielding, nutritious, and provides good income.
- Taro/Cocoyam: Traditional crop in West and Central Africa and Pacific islands. Shade-tolerant, grown in forest margins.
- Enset (false banana): Unique to Ethiopia. Provides starch from the stem. Drought-resistant, feeds millions in southern Ethiopia.

### Root Crop Management
- Vegetative propagation: Most root crops are planted from cuttings or seed tubers, not true seed. Clean planting material is essential.
- Soil requirements: Well-drained, loose soils preferred. Ridge or mound planting improves tuber development.
- Harvesting and storage: Root crops are perishable. Cassava must be processed within 24-48 hours of harvest. Improved storage techniques (sand storage for sweet potato, wax coating for yam) reduce losses.""",

        "ch16_energy_crops": """# Chapter 16: Energy and Industrial Crops

## Bioenergy and Industrial Crop Production

These crops provide raw materials for industry and energy, offering income diversification for African farmers.

### Key Crops
- Sugarcane: Major crop in Southern Africa (South Africa, Eswatini), East Africa (Kenya, Tanzania), and North Africa (Egypt). Used for sugar, ethanol, and electricity generation from bagasse.
- Cotton: Important cash crop across West Africa (Mali, Burkina Faso, Benin), East Africa, and Zimbabwe. Provides fibre, cottonseed oil, and animal feed.
- Tobacco: Significant in Southern Africa (Zimbabwe, Malawi, Mozambique). High-value but controversial due to health concerns.
- Jatropha: Promoted for biodiesel production in Africa, but many projects failed due to unrealistic yield expectations. Can succeed on marginal lands with realistic management.
- Sisal: Fibre crop grown in Tanzania, Kenya, and Madagascar. Used for rope, twine, and composite materials.""",

        "ch17_fresh_produce": """# Chapter 17: Fresh Produce

## Fruit and Vegetable Production

Horticulture is one of the fastest-growing agricultural sectors in Africa.

### Major Fresh Produce in Africa
- Tomatoes: Most widely grown vegetable across Africa. Nigeria, Egypt, and Morocco are major producers.
- Onions: Important cash crop in West Africa and East Africa. Storage onions provide income during off-season.
- Cabbages and leafy vegetables: Critical for nutrition. Traditional African vegetables (amaranth, spider plant, African nightshade) are gaining recognition.
- Mangoes: Widely grown across tropical Africa. Export potential limited by fruit fly damage.
- Citrus: Major production in North Africa (Morocco, Egypt), South Africa, and West Africa.
- Avocados: Kenya is a major exporter. Growing rapidly in Ethiopia and Tanzania.

### Key Challenges
- Perishability: Fresh produce losses of 30-50% are common in Africa due to poor cold chain infrastructure.
- Market access: Smallholders struggle to meet quality standards for formal markets and export.
- Pest and disease: Fruit flies, bacterial wilt, late blight require integrated management approaches.

### Opportunities
- Export horticulture: Kenya's fresh vegetable exports to Europe generate significant foreign exchange.
- Urban markets: Rapidly growing demand for diverse, quality fresh produce in African cities.
- Processing: Solar drying, canning, and juice production add value and reduce losses.""",

        "ch18_forage_crops": """# Chapter 18: Arable Forage Crops

## Forage and Fodder Production for Livestock

Adequate livestock feed is one of the biggest constraints to animal productivity in Africa.

### Forage Crop Types
- Grasses: Napier grass (Pennisetum purpureum) is the most important planted forage in East Africa. Very high-yielding (40-80 tonnes fresh matter/ha). Brachiaria species are increasingly important in tropical Africa.
- Legumes: Desmodium, Stylosanthes, Lablab, and Leucaena provide protein-rich feed and fix nitrogen.
- Dual-purpose crops: Cowpea, groundnut, and soybean provide both grain and fodder. Crop residues (maize stover, sorghum stover) are major dry-season feed sources.

### Feed Conservation
- Hay making: Cutting and drying forage for storage. Requires dry weather for successful curing.
- Silage: Fermented forage stored in airtight conditions. Increasingly adopted by dairy farmers in East Africa using tube silage and bag silage techniques.
- Crop residue treatment: Urea treatment of maize stover improves digestibility and protein content.""",

        "ch19_20_21_22_grassland": """# Chapters 19-22: Grassland Production and Management

## Pasture and Rangeland Management in Africa

Grasslands and rangelands cover vast areas of Africa and support millions of livestock.

### Grassland Types in Africa
- Tropical savanna: Mixed grass and tree vegetation across large areas of sub-Saharan Africa. Supports pastoral and agro-pastoral systems.
- Temperate grasslands: High-altitude grasslands in South Africa, Ethiopia, and Kenya. Support dairy and beef production.
- Semi-arid rangelands: Low rainfall areas supporting nomadic pastoralism. Fragile ecosystems vulnerable to overgrazing.

### Pasture Establishment
- Natural pasture improvement: Overseeding with improved species, fertilisation, and controlled grazing can double carrying capacity.
- Planted pastures: Establishing improved grasses and legumes on prepared land. Higher cost but much more productive.
- Species selection: Choose species adapted to local climate, soil, and management intensity.

### Grazing Management
- Rotational grazing: Dividing pasture into paddocks and moving animals between them. Allows rest and recovery.
- Carrying capacity: Matching animal numbers to available forage. Overstocking is the primary cause of rangeland degradation in Africa.
- Dry season management: Strategic supplementary feeding, hay reserves, and destocking during drought.

### Pasture Conservation
- Hay: Simple technology for preserving forage. Requires 2-3 consecutive dry days for curing.
- Silage: Higher nutritional value than hay but requires more infrastructure. Increasingly popular in East African dairy systems.
- Standing hay: Leaving mature grass ungrazed as a dry season reserve. Nutritional value declines but provides critical roughage."""
    }

    print(f"\n--- Generating Lockhart & Wiseman chapter notes ---")
    for filename, content in chapters.items():
        filepath = os.path.join(lw_dir, f"{filename}.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  [OK] Saved {filename}.md")

def scrape_additional_agriculture():
    """Scrape additional agricultural resources for Africa."""
    africa_dir = os.path.join(KNOWLEDGE_DIR, "african_agriculture")
    ensure_dir(africa_dir)

    urls = [
        ("https://en.wikipedia.org/wiki/Agriculture_in_Africa", "agriculture_in_africa.md"),
        ("https://en.wikipedia.org/wiki/Lumpy_skin_disease", "lumpy_skin_disease.md"),
        ("https://en.wikipedia.org/wiki/Fall_armyworm", "fall_armyworm.md"),
        ("https://en.wikipedia.org/wiki/Cassava", "cassava.md"),
        ("https://en.wikipedia.org/wiki/Maize", "maize.md"),
        ("https://en.wikipedia.org/wiki/Striga", "striga_witchweed.md"),
        ("https://en.wikipedia.org/wiki/Conservation_agriculture", "conservation_agriculture.md"),
        ("https://en.wikipedia.org/wiki/Agroforestry", "agroforestry.md"),
        ("https://en.wikipedia.org/wiki/Push%E2%80%93pull_agricultural_pest_management", "push_pull_technology.md"),
        ("https://en.wikipedia.org/wiki/East_Coast_fever", "east_coast_fever.md"),
        ("https://en.wikipedia.org/wiki/African_swine_fever", "african_swine_fever.md"),
        ("https://en.wikipedia.org/wiki/Newcastle_disease", "newcastle_disease.md"),
        ("https://en.wikipedia.org/wiki/Foot-and-mouth_disease", "foot_and_mouth_disease.md"),
    ]

    print(f"\n--- Scraping Wikipedia agriculture articles ---")
    for url, filename in urls:
        print(f"  Fetching {url}...")
        content = fetch_url(url)
        if content and len(content) > 500:
            filepath = os.path.join(africa_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {filename.replace('.md','').replace('_',' ').title()}\n\n")
                f.write(f"Source: {url}\n\n")
                # Trim to reasonable size (first ~15000 chars)
                f.write(content[:15000])
            print(f"  [OK] Saved {filename}")
        else:
            print(f"  [SKIP] No useful content for {filename}")
        time.sleep(1)


if __name__ == "__main__":
    print("=" * 60)
    print("AgriMate Knowledge Base Builder")
    print("=" * 60)

    # 1. Generate Lockhart & Wiseman chapter notes (instant, no internet)
    generate_lockhart_wiseman()

    # 2. Scrape FAO documents
    scrape_fao_documents()

    # 3. Scrape additional Wikipedia articles on African agriculture
    scrape_additional_agriculture()

    # Count total files
    total = 0
    for root, dirs, files in os.walk(KNOWLEDGE_DIR):
        total += len([f for f in files if f.endswith('.md')])

    print(f"\n{'=' * 60}")
    print(f"DONE. Total knowledge base files: {total}")
    print(f"Location: {KNOWLEDGE_DIR}")
    print(f"{'=' * 60}")

"""Rule-based role taxonomy for job titles (same rules as Task 3 of the notebook).

The FIRST matching rule wins, so specific roles are listed before general ones.
Titles that match nothing are labelled "Other". Input must be a CLEANED title
(lowercase, punctuation removed), e.g. from recommender.clean_title().
"""
import re

ROLES = [
    ("AI / ML engineer", r"\bai\b|artificial intelligence|machine learning|\bml\b|chatgpt|openai|\bllm\b|chatbot|\bgpt"),
    ("Automation / no-code", r"zapier|automation|gohighlevel|airtable|\bn8n\b|no code|nocode|make com|\bbubble\b"),
    ("Data analyst / scientist", r"data analy|data scien|data engineer|power bi|tableau|\bsql\b|scraping|scraper|dashboard|\betl\b|big data"),
    ("Data entry", r"data entry|copy paste|copy and paste|typing"),
    ("Virtual assistant", r"virtual assistant|\bva\b|executive assistant|admin assistant|administrative assistant|personal assistant|\bassistant\b"),
    ("Recruiter / HR", r"recruit|talent|human resources|\bhr\b|hiring|sourcer"),
    ("Sales & lead generation", r"lead gen|appointment setter|cold call|sales rep|\bcloser\b|\bsdr\b|telemarket|\bsales\b|setter|outreach|prospecting"),
    ("Customer support / chat", r"customer service|customer support|support agent|call cent|chat support|chatter|customer success|support specialist"),
    ("Social media manager", r"social media|community manag|tiktok|instagram|linkedin|influencer|facebook page|\bugc\b"),
    ("Ads / PPC", r"google ads|facebook ads|meta ads|\bppc\b|media buy|ads manager|ads expert|paid ads|\bads\b|advertis"),
    ("SEO", r"\bseo\b|search engine"),
    ("Email marketing", r"email market|cold email|newsletter|klaviyo|mailchimp|email campaign"),
    ("Blockchain / crypto", r"crypto|blockchain|web3|\bnft\b|solidity|smart contract|defi|bitcoin|token"),
    ("Mobile app developer", r"mobile app|android|\bios\b|flutter|react native|swift|app developer|app development|kotlin|\bapp\b"),
    ("DevOps / cloud / security", r"devops|\baws\b|azure|cloud|kubernetes|docker|sysadmin|network engineer|cyber|security|penetration|server"),
    ("Game developer", r"unity|unreal|game develop|game design|roblox|\bgame\b"),
    ("QA / tester", r"\bqa\b|tester|testing|quality assurance"),
    ("Shopify developer", r"shopify"),
    ("Amazon / e-commerce", r"amazon|\bfba\b|ebay|etsy|walmart|dropship|e commerce|ecommerce|product listing|tiktok shop"),
    ("WordPress / website builder", r"wordpress|elementor|woocommerce|\bdivi\b|\bwix\b|squarespace|webflow|web design|website design|landing page|\bwebsite\b|\bsite\b"),
    ("Web / software developer", r"web develop|full stack|fullstack|front end|frontend|back end|backend|react|\bnode|javascript|\bphp\b|laravel|django|flask|angular|\bvue\b|next js|\bjs\b|python|software|\bdeveloper\b|\bengineer\b|programmer|\bapi\b|\bnet\b|java\b"),
    ("UI / UX designer", r"\bui\b|\bux\b|figma|user interface|user experience|wireframe"),
    ("Logo / brand designer", r"logo|brand identity|branding|brand design"),
    ("3D / animation", r"3d|animat|blender|rendering|\bcad\b|motion graphic|after effects|architectural|autocad|revit"),
    ("Video editor", r"video edit|video editor|\bediting\b|youtube video|youtube editor|short form|reels|\bvideo\b|videograph|thumbnail"),
    ("Voice / audio / music", r"voice|audio|podcast|music|singer|sound|mixing|mastering|\bvo\b|narrat"),
    ("Translation / transcription", r"translat|transcri|subtitl|interpret|proofread"),
    ("Writer / copywriter", r"writer|writing|copywrit|content|blog|article|ghostwrit|script|\bbook\b|ebook|editor"),
    ("Illustrator / graphic designer", r"illustrat|graphic|designer|design|cartoon|comic|photoshop|canva|poster|flyer|banner|packaging|infographic|photo|\bart\b"),
    ("Finance / legal", r"bookkeep|accountant|accounting|\bcpa\b|\btax\b|quickbooks|financial|finance|payroll|lawyer|attorney|legal|paralegal|grant|invoice"),
    ("Project / product manager", r"project manag|product manag|scrum|operations manag|program manag|\bpm\b|\bmanager\b"),
    ("Research / tutoring", r"research|tutor|teacher|survey|lesson|course|\bteach"),
    ("Excel / spreadsheet", r"excel|spreadsheet|google sheets|\bsheets\b|\bpdf\b"),
    ("Consulting / coaching", r"consult|coach|mentor|advisor|strategist"),
    ("Marketing (general)", r"marketing|marketer|growth|brand"),
]

ROLE_PATTERNS = [(name, re.compile(pat)) for name, pat in ROLES]


def assign_role(title_clean: str) -> str:
    for name, pat in ROLE_PATTERNS:
        if pat.search(title_clean):
            return name
    return "Other"

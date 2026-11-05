"""Source of the STARTER gold-standard file (eval/gold/gold_codes.csv).

!!! These codes are DRAFTS, NOT a validated gold standard. !!!

They were drafted by the AI coding assistant that helped scaffold this repo,
working from Federal Register abstracts and keyword-located passages, so that
the evaluation pipeline has something to run on. They have NOT been reviewed by
a trained human coder. Every row is written with status "draft_unverified" and
coder_id "assistant-draft". Rows whose answer was unclear are left as "todo"
for a human to code from scratch.

To turn this into a real gold standard, a human coder should open
eval/gold/gold_codes.csv, code each document independently from the full text
(ideally without looking at the draft), then set status to "verified" and
coder_id to their own ID. See docs/evaluation_protocol.md.

Run:  python eval/gold/starter_drafts.py   (rewrites gold_codes.csv; fails if
any quote is not found verbatim in the committed corpus snapshot).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from policylab.codebook import load_codebook  # noqa: E402
from policylab.store import load_corpus  # noqa: E402
from policylab.textutil import quote_in  # noqa: E402

FIELDS = ["doc_number", "variable", "gold_values", "evidence_chunk_id", "evidence_quote",
          "status", "coder_id", "coded_on", "notes"]

# doc -> variable -> (values, quote, note). values=None means "todo" (left for a human).
D: dict[str, dict[str, tuple]] = {
    "2024-08098": {
        "policy_domain": (["nutrition"], "This rulemaking finalizes long-term school nutrition requirements", ""),
        "populations": (["school_age_children", "young_children", "low_income", "tribal_communities"],
                        "phases in added sugars limits for the school lunch and breakfast programs and in the Child and Adult Care Food Program",
                        "young_children via CACFP cereal/yogurt limits; tribal via vegetable-for-grain substitution; verify"),
        "settings": (["schools", "child_care"], "phases in added sugars limits for the school lunch and breakfast programs and in the Child and Adult Care Food Program", ""),
        "mechanisms": (["nutrition_standard", "procurement"], "this rule includes provisions that strengthen Buy American requirements", ""),
        "legal_force": (["mandatory"], "This rulemaking finalizes long-term school nutrition requirements", ""),
        "regulatory_stage": (["final_rule"], "ACTION: Final rule.", ""),
        "effective_date": (["2024-07-01"], "This final rule is effective July 1, 2024.", "phased compliance dates differ by provision"),
        "nutrients_targeted": (["added_sugars", "sodium", "milk_dairy", "whole_grains"],
                               "this final rule implements a single sodium reduction in the school lunch and breakfast programs", ""),
        "equity_provisions": (["yes"], "Substituting Vegetables for Grains in Tribal Communities", "cultural accommodation for Tribal communities; borderline, verify"),
        "evaluation_reporting": (["yes"], "commits to studying the potential associations between sodium reduction and student participation", ""),
        "public_comment": (["no"], "", ""),
    },
    "2022-02327": {
        "policy_domain": (["nutrition"], "This final rule will establish transitional standards to support the continued provision of nutritious school meals", ""),
        "populations": (["school_age_children", "low_income"], "for students in grades K through 12", ""),
        "settings": (["schools"], "allowing local operators of the National School Lunch Program and School Breakfast Program to offer flavored, low-fat milk", ""),
        "mechanisms": (["nutrition_standard"], "This final rule will establish transitional standards", ""),
        "legal_force": (["mandatory"], "This final rule will establish transitional standards", ""),
        "regulatory_stage": (["final_rule"], "ACTION: Final rule with request for comments.", ""),
        "effective_date": (["2022-07-01"], "This final rule will become effective July 1, 2022.", ""),
        "nutrients_targeted": (["milk_dairy", "whole_grains", "sodium"], "Transitional Standards for Milk, Whole Grains, and Sodium", ""),
        "equity_provisions": (["no"], "", ""),
        "evaluation_reporting": (None, "", "todo: check preamble for reporting changes"),
        "public_comment": (["yes"], "ACTION: Final rule with request for comments.", ""),
    },
    "2026-09212": {
        "policy_domain": (["nutrition"], "expands fluid milk options", ""),
        "populations": (["young_children", "school_age_children", "low_income"], "to participants two years and older",
                        "CACFP adult participants may also be covered; consider older_adults"),
        "settings": (["schools", "child_care"], "allowing schools and child and adult care providers participating in Child Nutrition Programs to offer whole and reduced-fat milk", ""),
        "mechanisms": (["nutrition_standard"], "This rule codifies milkfat requirements following enactment of the Whole Milk for Healthy Kids Act", ""),
        "legal_force": (["mandatory"], "This rule codifies milkfat requirements", "deregulatory: permits rather than requires; verify"),
        "regulatory_stage": (["final_rule"], "ACTION: Final rule with comment period.", ""),
        "effective_date": (["2026-06-08"], "This rule is effective June 8, 2026.", ""),
        "nutrients_targeted": (["milk_dairy"], "offer whole and reduced-fat milk", ""),
        "equity_provisions": (["no"], "", ""),
        "evaluation_reporting": (["no"], "", ""),
        "public_comment": (["yes"], "ACTION: Final rule with comment period.", ""),
    },
    "2024-30710": {
        "policy_domain": (["nutrition"], "crediting in the Child Nutrition Programs", ""),
        "populations": (["school_age_children", "young_children", "low_income"], "crediting in the Child Nutrition Programs", ""),
        "settings": (["schools", "child_care"], "crediting in the Child Nutrition Programs", "verify child_care (CACFP is a Child Nutrition Program)"),
        "mechanisms": (["advisory_process"], "requests comments from the public to help inform future policymaking", ""),
        "legal_force": (["not_applicable"], "ACTION: Notice; Request for Information.", ""),
        "regulatory_stage": (["meeting_or_comment_request"], "ACTION: Notice; Request for Information.", ""),
        "effective_date": (["not_stated"], "", ""),
        "nutrients_targeted": (["added_sugars", "milk_dairy", "other_nutrients"], "high-protein yogurt", "grain-based desserts relate to added sugars"),
        "equity_provisions": (["no"], "", ""),
        "evaluation_reporting": (["no"], "", ""),
        "public_comment": (["yes"], "Written comments must be received on or before March 26, 2025.", ""),
    },
    "2016-17227": {
        "policy_domain": (["nutrition"], "nutrition standards for all foods sold in schools", ""),
        "populations": (["school_age_children"], "nutrition standards for all foods sold in schools", ""),
        "settings": (["schools"], "nutrition standards for all foods sold in schools", ""),
        "mechanisms": (["nutrition_standard"], "nutrition standards for all foods sold in schools", ""),
        "legal_force": (["mandatory"], "Local educational agencies and school food authorities would be required to maintain records documenting compliance", ""),
        "regulatory_stage": (["final_rule"], "ACTION: Final rule and interim final rule.", "total fat standard retained as interim"),
        "effective_date": (["2016-09-27"], "This final rule is effective September 27, 2016.", ""),
        "nutrients_targeted": (None, "", "todo: Smart Snacks limits (calories, sodium, fats, sugars, whole grain-rich); confirm from regulatory text"),
        "equity_provisions": (["no"], "", ""),
        "evaluation_reporting": (["yes"], "Local educational agencies and school food authorities would be required to maintain records documenting compliance", ""),
        "public_comment": (["yes"], "Comments on the interim final rule total fat standard must be submitted by September 27, 2016.", ""),
    },
    "2016-17230": {
        "policy_domain": (["multiple"], "local school wellness policies must include specific goals for nutrition promotion and education, physical activity", ""),
        "populations": (["school_age_children"], "local educational agencies that participate in the National School Lunch and School Breakfast Programs", ""),
        "settings": (["schools"], "local educational agencies that participate in the National School Lunch and School Breakfast Programs", ""),
        "mechanisms": (["education_promotion", "data_collection_reporting"], "periodically assess and disclose to the public", ""),
        "legal_force": (["mandatory"], "This final rule requires all local educational agencies", ""),
        "regulatory_stage": (["final_rule"], "ACTION: Final rule.", ""),
        "effective_date": (["2016-08-29"], "This rule is effective August 29, 2016.", ""),
        "nutrients_targeted": (["none"], "", ""),
        "equity_provisions": (["no"], "", ""),
        "evaluation_reporting": (["yes"], "periodically assess and disclose to the public", ""),
        "public_comment": (["no"], "", ""),
    },
    "2016-09412": {
        "policy_domain": (["nutrition"], "updates the meal pattern requirements for the Child and Adult Care Food Program", ""),
        "populations": (["infants_toddlers", "young_children", "school_age_children", "older_adults"],
                        "supports mothers who breastfeed", "older_adults via adult day care; consider low_income and pregnant_postpartum; verify"),
        "settings": (["child_care"], "requires centers and day care homes participating in the Child and Adult Care Food Program", "adult day care also covered"),
        "mechanisms": (["nutrition_standard"], "updates the meal pattern requirements", ""),
        "legal_force": (["mandatory"], "This rule requires centers and day care homes", ""),
        "regulatory_stage": (["final_rule"], "ACTION: Final rule.", ""),
        "effective_date": (["2016-06-24"], "This rule is effective June 24, 2016.", ""),
        "nutrients_targeted": (["whole_grains", "fruits_vegetables", "added_sugars", "milk_dairy"],
                               "serve more whole grains and a greater variety of vegetables and fruit, and reduces the amount of added sugars", ""),
        "equity_provisions": (["no"], "", ""),
        "evaluation_reporting": (None, "", "todo"),
        "public_comment": (["no"], "", ""),
    },
    "2024-07437": {
        "policy_domain": (["nutrition"], "align the WIC food packages with the current Dietary Guidelines for Americans", ""),
        "populations": (["pregnant_postpartum", "infants_toddlers", "young_children", "low_income"],
                        "strengthens support for individual breastfeeding goals", ""),
        "settings": (["food_assistance_programs"], "provide WIC State agencies with greater flexibility to prescribe and tailor food packages", "check vendor/retailer changes"),
        "mechanisms": (["nutrition_standard"], "revises regulations to align the WIC food packages", ""),
        "legal_force": (["mandatory"], "revises regulations to align the WIC food packages", ""),
        "regulatory_stage": (["final_rule"], "ACTION: Final rule.", ""),
        "effective_date": (["2024-06-17"], "This rule is effective June 17, 2024.", ""),
        "nutrients_targeted": (["fruits_vegetables", "milk_dairy", "whole_grains"], "encourages fruit and vegetable consumption", "verify additional nutrients (e.g., juice, added sugars, sodium)"),
        "equity_provisions": (["yes"], "promoting nutrition security and equity", ""),
        "evaluation_reporting": (None, "", "todo"),
        "public_comment": (["no"], "", ""),
    },
    "2026-12700": {
        "policy_domain": (["nutrition"], "revised the WIC food package regulations", ""),
        "populations": (["pregnant_postpartum", "infants_toddlers", "young_children", "low_income"],
                        "Special Supplemental Nutrition Program for Women, Infants, and Children", "inherits WIC populations"),
        "settings": (["food_assistance_programs"], "extends the implementation date for WIC State agencies", ""),
        "mechanisms": (["nutrition_standard"], "vitamin D fortification requirement for yogurts", ""),
        "legal_force": (["mandatory"], "vitamin D fortification requirement for yogurts", ""),
        "regulatory_stage": (["correction_or_technical"], "ACTION: Final rule; technical corrections.", ""),
        "effective_date": (["2026-06-24"], "This rule is effective on June 24, 2026.", ""),
        "nutrients_targeted": (["other_nutrients", "milk_dairy"], "vitamin D fortification requirement for yogurts", ""),
        "equity_provisions": (["no"], "", ""),
        "evaluation_reporting": (["no"], "", ""),
        "public_comment": (["no"], "", "excepted from notice and comment"),
    },
    "2014-27834": {
        "policy_domain": (["nutrition"], "establishing requirements for providing calorie declarations for food sold from certain vending machines", ""),
        "populations": (["general_population"], "does not permit a prospective purchaser to examine the Nutrition Facts Panel", ""),
        "settings": (["restaurants_food_service"], "food sold from certain vending machines", "codebook places vending under restaurants_food_service"),
        "mechanisms": (["labeling_disclosure"], "establishing requirements for providing calorie declarations", ""),
        "legal_force": (["mandatory"], "establishing requirements for providing calorie declarations", "voluntary registration option for non-covered operators"),
        "regulatory_stage": (["final_rule"], "ACTION: Final rule.", ""),
        "effective_date": (["2016-12-01"], "Effective Date: December 1, 2016.", ""),
        "nutrients_targeted": (["calories"], "calorie declarations", ""),
        "equity_provisions": (["no"], "", ""),
        "evaluation_reporting": (["no"], "", ""),
        "public_comment": (["no"], "", ""),
    },
    "2023-27450": {
        "policy_domain": (["nutrition"], "Menu Labeling: Supplemental Guidance for Industry (Edition 2)", ""),
        "populations": (["general_population"], "voluntary declaration of nutrition information for menus on third-party platforms", ""),
        "settings": (["restaurants_food_service"], "voluntary declaration of nutrition information for menus on third-party platforms", ""),
        "mechanisms": (["labeling_disclosure", "voluntary_target_guidance"], "announcing the availability of a draft guidance for industry", ""),
        "legal_force": (["voluntary"], "address voluntary declaration of added sugars", ""),
        "regulatory_stage": (["guidance_availability"], "ACTION: Notification of availability.", "FR lists this as a Proposed Rule document type"),
        "effective_date": (["not_stated"], "", ""),
        "nutrients_targeted": (["added_sugars"], "voluntary declaration of added sugars", ""),
        "equity_provisions": (["no"], "", ""),
        "evaluation_reporting": (["no"], "", ""),
        "public_comment": (["yes"], "Submit either electronic or written comments on the draft guidance by February 12, 2024", ""),
    },
    "2025-00778": {
        "policy_domain": (["nutrition"], "proposes to require front-of-package nutrition labels", ""),
        "populations": (["general_population"], "The box would provide consumers, including those who have lower nutrition knowledge", ""),
        "settings": (["packaged_food_supply"], "on most foods that must bear a Nutrition Facts label", ""),
        "mechanisms": (["labeling_disclosure"], "proposes to require front-of-package nutrition labels", ""),
        "legal_force": (["mandatory"], "proposes to require front-of-package nutrition labels", "proposed binding requirement"),
        "regulatory_stage": (["proposed_rule"], "ACTION: Proposed rule.", ""),
        "effective_date": (["not_stated"], "", ""),
        "nutrients_targeted": (["saturated_fat", "sodium", "added_sugars"], "limit their intake of saturated fat, sodium, and added sugars", "quote is from DGA background; FOP box lists the same three nutrients"),
        "equity_provisions": (["yes"], "advance health equity", ""),
        "evaluation_reporting": (["yes"], "the accuracy of the provided burden estimates", "PRA collection of information"),
        "public_comment": (["yes"], "Either electronic or written comments on the proposed rule must be submitted by May 16, 2025.", ""),
    },
    "2024-29957": {
        "policy_domain": (["nutrition"], "updating the definition for the implied nutrient content claim", ""),
        "populations": (["general_population"], "help consumers identify foods", ""),
        "settings": (["packaged_food_supply"], "in the labeling of human food products", ""),
        "mechanisms": (["labeling_disclosure"], "revises the requirements for when the term", ""),
        "legal_force": (["mandatory"], "revises the requirements for when the term", "claim is voluntary, criteria binding when used; candidate for 'mixed'"),
        "regulatory_stage": (["final_rule"], "ACTION: Final rule.", ""),
        "effective_date": (["2025-02-25"], "This rule is effective February 25, 2025.", "compliance date 2028-02-25"),
        "nutrients_targeted": (None, "", "todo: food group equivalents + nutrients to limit (sodium, saturated fat, added sugars); confirm"),
        "equity_provisions": (["yes"], "Doing so will advance health equity", ""),
        "evaluation_reporting": (["yes"], "Require the establishment and maintenance of certain records", ""),
        "public_comment": (["no"], "", ""),
    },
    "2024-25567": {
        "policy_domain": (["nutrition"], "sodium reduction in a variety of identified categories of foods", ""),
        "populations": (["general_population"], "excessive intake of sodium in the current population", ""),
        "settings": (["packaged_food_supply"], "commercially processed, packaged, or prepared", ""),
        "mechanisms": (["voluntary_target_guidance"], "the next voluntary goals", ""),
        "legal_force": (["voluntary"], "the next voluntary goals", ""),
        "regulatory_stage": (["correction_or_technical"], "ACTION: Notice of availability; extension of comment period.", "extension of comment period"),
        "effective_date": (["not_stated"], "", ""),
        "nutrients_targeted": (["sodium"], "the next voluntary goals (Phase II (3-year)) for sodium reduction", ""),
        "equity_provisions": (["yes"], "advance health equity by supporting a healthier food supply", ""),
        "evaluation_reporting": (["no"], "", ""),
        "public_comment": (["yes"], "Submit either electronic or written comments on the draft guidance by January 13, 2025", ""),
    },
    "2026-18897": {
        "policy_domain": (["nutrition"], "exclude “sugar- sweetened beverages”", ""),
        "populations": (["low_income"], "amend the SNAP definition of food for purchase", ""),
        "settings": (["retail_food_stores", "food_assistance_programs"], "amend the SNAP definition of food for purchase", ""),
        "mechanisms": (["advisory_process"], "This notice invites the public to comment", "the underlying demonstration is a purchase restriction"),
        "legal_force": (["not_applicable"], "This notice invites the public to comment", ""),
        "regulatory_stage": (["meeting_or_comment_request"], "ACTION: Notice of request for public comments.", ""),
        "effective_date": (["not_stated"], "", ""),
        "nutrients_targeted": (["added_sugars"], "exclude “sugar- sweetened beverages”", ""),
        "equity_provisions": (["no"], "", ""),
        "evaluation_reporting": (["yes"], "FNA will carefully review the results of the project based on the State's evaluation data", ""),
        "public_comment": (["yes"], "Written comments must be received on or before October 15, 2026.", ""),
    },
    "2024-29100": {
        "policy_domain": (["nutrition"], "Scientific Report of the 2025 Dietary Guidelines Advisory Committee", ""),
        "populations": (["general_population"], "invite the public to provide written comments", ""),
        "settings": (["other"], "invite the public to provide written comments", "no setting-specific provisions"),
        "mechanisms": (["advisory_process"], "invite the public to provide written comments and virtual oral comments on the Scientific Report", ""),
        "legal_force": (["not_applicable"], "invite the public to provide written comments", ""),
        "regulatory_stage": (["meeting_or_comment_request"], "Notice and request for public comments on the Scientific Report", ""),
        "effective_date": (["not_stated"], "", ""),
        "nutrients_targeted": (["none"], "", ""),
        "equity_provisions": (["no"], "", ""),
        "evaluation_reporting": (["no"], "", ""),
        "public_comment": (["yes"], "invite the public to provide written comments and virtual oral comments", ""),
    },
    "2026-20833": {
        "policy_domain": (["physical_activity"], "adding new, science-based step count and muscle-strengthening activity guidance", ""),
        "populations": (["general_population"], "announces the solicitation of public comments", "verify age groups in guidance scope"),
        "settings": (["other"], "announces the solicitation of public comments", ""),
        "mechanisms": (["advisory_process"], "announces the solicitation of public comments", ""),
        "legal_force": (["not_applicable"], "announces the solicitation of public comments", ""),
        "regulatory_stage": (["meeting_or_comment_request"], "announces the solicitation of public comments", "ACTION line just says Notice"),
        "effective_date": (["not_stated"], "", ""),
        "nutrients_targeted": (["none"], "", ""),
        "equity_provisions": (["no"], "", ""),
        "evaluation_reporting": (["no"], "", ""),
        "public_comment": (["yes"], "Written comments will be accepted through 11:59 p.m.", ""),
    },
    "2025-15011": {
        "policy_domain": (["multiple"], "youth sports, fitness, and nutrition", "fitness test is PA; council scope includes nutrition"),
        "populations": (["school_age_children"], "youth sports, fitness, and nutrition", ""),
        "settings": (["schools"], "school-based programs that reward excellence in physical education", ""),
        "mechanisms": (["education_promotion", "incentive", "advisory_process"], "Presidential challenges and school-based programs that reward excellence in physical education", ""),
        "legal_force": (None, "", "todo: executive order binds agencies, not the public; decide mandatory vs not_applicable"),
        "regulatory_stage": (["presidential_document"], "it is hereby ordered", ""),
        "effective_date": (["not_stated"], "", ""),
        "nutrients_targeted": (["none"], "", ""),
        "equity_provisions": (["no"], "", ""),
        "evaluation_reporting": (None, "", "todo"),
        "public_comment": (["no"], "", ""),
    },
    "2024-08758": {
        "policy_domain": (["physical_activity"], "safe, accessible, and equitable pedestrian and bicycle network connectivity", "active transportation counts as physical_activity"),
        "populations": (["general_population"], "The ATIIP grants will allow communities to identify, prioritize, and implement improvements", ""),
        "settings": (["community_built_environment"], "pedestrian and bicycle network connectivity", ""),
        "mechanisms": (["funding_grants", "infrastructure_design"], "Notice of Funding Opportunity (NOFO) for the Active Transportation Infrastructure Investment Program", ""),
        "legal_force": (["not_applicable"], "Notice of Funding Opportunity", ""),
        "regulatory_stage": (["funding_notice"], "Notice of Funding Opportunity (NOFO) for the Active Transportation Infrastructure Investment Program (ATIIP) is now available", ""),
        "effective_date": (["not_stated"], "", ""),
        "nutrients_targeted": (["none"], "", ""),
        "equity_provisions": (["yes"], "safe, accessible, and equitable pedestrian and bicycle network connectivity", ""),
        "evaluation_reporting": (["no"], "", ""),
        "public_comment": (["no"], "", ""),
    },
    "2024-08899": {
        "policy_domain": (["obesity_prevention_general"], "address preventable risk behaviors", "REACH spans nutrition, physical activity, tobacco"),
        "populations": (["racial_ethnic_minority_groups"], "Racial and Ethnic Approaches to Community Health", ""),
        "settings": (["other"], "community coalitions", "community programs; no built-environment provisions"),
        "mechanisms": (["incentive"], "No cash prize will be awarded.", "recognition award"),
        "legal_force": (["voluntary"], "The Challenge will accept applications", ""),
        "regulatory_stage": (["funding_notice"], "announces the 2024 Racial and Ethnic Approaches to Community Health (REACH) Lark Galloway-Gilliam for Advancing Health Equity Award Challenge", "award/challenge program"),
        "effective_date": (["not_stated"], "", ""),
        "nutrients_targeted": (["none"], "", ""),
        "equity_provisions": (["yes"], "culturally tailored interventions that advance health equity, reduce health disparities", ""),
        "evaluation_reporting": (["no"], "", ""),
        "public_comment": (["no"], "", ""),
    },
}


def main() -> None:
    corpus = load_corpus()
    cb = load_codebook()
    rows, errors = [], []
    for doc, codes in D.items():
        if doc not in corpus.documents:
            errors.append(f"{doc}: not in corpus")
            continue
        chunks = corpus.chunks_for(doc)
        for var in cb.ids:
            values, quote, note = codes.get(var, (None, "", "todo"))
            if values is None:
                rows.append({"doc_number": doc, "variable": var, "gold_values": "", "evidence_chunk_id": "",
                             "evidence_quote": "", "status": "todo", "coder_id": "", "coded_on": "",
                             "notes": note})
                continue
            errors += [f"{doc} {p}" for p in cb.get(var).validate_values(values)]
            cid = ""
            if quote:
                cid = next((c["chunk_id"] for c in chunks if quote_in(quote, c["text"])), "")
                if not cid:
                    errors.append(f"{doc} {var}: quote not found: {quote!r}")
            rows.append({"doc_number": doc, "variable": var, "gold_values": ";".join(values),
                         "evidence_chunk_id": cid, "evidence_quote": quote, "status": "draft_unverified",
                         "coder_id": "assistant-draft", "coded_on": "2026-11-05", "notes": note})
    if errors:
        raise SystemExit("\n".join(errors))
    out = ROOT / "eval" / "gold" / "gold_codes.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    template = ROOT / "eval" / "gold" / "gold_codes_template.csv"
    with open(template, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for doc in D:
            for var in cb.ids:
                w.writerow({"doc_number": doc, "variable": var, "gold_values": "", "evidence_chunk_id": "",
                            "evidence_quote": "", "status": "todo", "coder_id": "", "coded_on": "", "notes": ""})
    print(f"wrote {len(rows)} rows to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

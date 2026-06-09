"""
Crawler TikTok Creative Center Top Ads.
"""

import os
import json
import time
import argparse
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright, Response

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def parse_country_codes(country_arg: str | None, countries_arg: str | None) -> list[str]:
    raw_codes = countries_arg or country_arg or "VN"
    countries = []
    for code in raw_codes.split(","):
        normalized = code.strip().upper()
        if normalized and normalized not in countries:
            countries.append(normalized)
    return countries or ["VN"]


def build_url(period: int, country: str) -> str:
    return (
        f"https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en"
        f"?period={period}&region={country}"
    )


def crawl_topads(period: int = 30, country: str = "VN", limit: int = 20) -> dict:
    country = country.upper()
    collected = {
        "crawled_at"   : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "period"       : period,
        "country_code" : country,
        "top_ads_list" : None,
        "filters"      : None,
        "all_responses": []
    }

    collected_ads = []
    ad_ids_seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page    = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        def handle_response(response: Response):
            url = response.url
            if "creative_radar_api" not in url:
                return
            try:
                data     = response.json()
                endpoint = url.split("creative_radar_api/v1/")[-1].split("?")[0]
                print(f"[{response.status}] {endpoint}")

                collected["all_responses"].append({
                    "endpoint" : endpoint,
                    "full_url" : url,
                    "status"   : response.status,
                    "data"     : data
                })

                if "top_ads/v2/list" in url:
                    materials = data.get("data", {}).get("materials", data.get("data", {}).get("list", []))
                    for ad in materials:
                        ad_id = ad.get("id")
                        if ad_id and ad_id not in ad_ids_seen:
                            ad_ids_seen.add(ad_id)
                            ad["country_code"] = country
                            collected_ads.append(ad)
                elif "top_ads/v2/filters" in url and collected["filters"] is None:
                    collected["filters"] = data

            except Exception:
                pass

        page.on("response", handle_response)

        target_url = build_url(period, country)
        print(f"[INFO] Navigating to URL: {target_url}")
        page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

        print("[INFO] Waiting for 15 seconds for initial load...")
        time.sleep(15)

        # Pagination & Scrolling loop to collect more ads (3 pages ~ 60 ads)
        pages_to_crawl = 3
        for page_num in range(1, pages_to_crawl):
            print(f"[INFO] Scrolling and attempting to load page {page_num + 1}...")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

            # Look for next pagination button
            next_button_selectors = [
                ".ant-pagination-next:not(.ant-pagination-disabled)",
                "li.ant-pagination-next",
                "button[aria-label='Next Page']"
            ]
            clicked = False
            for selector in next_button_selectors:
                try:
                    locator = page.locator(selector)
                    if locator.is_visible() and locator.is_enabled():
                        locator.click()
                        print(f"[INFO] Clicked next page button: {selector}")
                        time.sleep(5)
                        clicked = True
                        break
                except Exception:
                    pass
            
            if not clicked:
                print("[INFO] No next page button clicked. Performing extra scroll down.")
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)

        print(f"[INFO] Finished crawling. Total unique ads collected: {len(collected_ads)}")

        # Construct final top_ads_list format expected by load.py
        collected["top_ads_list"] = {
            "code": 0,
            "msg": "OK",
            "data": {
                "materials": collected_ads
            }
        }

        today_str = datetime.now().strftime("%Y-%m-%d")
        raw_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), f"../data/raw/tiktok_creative_center/{today_str}")
        )
        os.makedirs(raw_dir, exist_ok=True)

        browser.close()

    return collected


def combine_country_results(country_results: list[dict]) -> dict:
    all_ads = []
    for result in country_results:
        country_code = result.get("country_code")
        materials = result.get("top_ads_list", {}).get("data", {}).get("materials", [])
        for ad in materials:
            ad["country_code"] = ad.get("country_code") or country_code
            all_ads.append(ad)

    return {
        "crawled_at"     : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "period"         : country_results[0].get("period") if country_results else None,
        "countries"      : [result.get("country_code") for result in country_results],
        "country_results": country_results,
        "top_ads_list"   : {
            "code": 0,
            "msg" : "OK",
            "data": {
                "materials": all_ads
            }
        },
        "filters"        : next((result.get("filters") for result in country_results if result.get("filters")), None),
        "all_responses"  : [
            response
            for result in country_results
            for response in result.get("all_responses", [])
        ]
    }


def write_raw_json(raw_dir: str, today_str: str, raw_data: dict, suffix: str | None = None) -> str:
    suffix_part = f"_{suffix}" if suffix else ""
    output_file = os.path.join(raw_dir, f"raw_topads_{today_str}{suffix_part}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=4)
    return output_file


def upload_raw_json(s3_key: str, raw_data: dict):
    try:
        from src.utils.s3 import upload_json_to_s3
        upload_json_to_s3(s3_key, raw_data)
    except Exception as e:
        print(f"[WARNING] Cannot upload data to S3: {e}")


def main():
    parser = argparse.ArgumentParser(description="TikTok Creative Center Top Ads Crawler")
    parser.add_argument("--period",  type=int, default=30,  help="Number of days (7 or 30)")
    parser.add_argument("--country", type=str, default="VN", help="Country code or comma-separated country codes (VN,US,TH...)")
    parser.add_argument("--countries", type=str, default=None, help="Comma-separated country codes to crawl (VN,US,TH...)")
    parser.add_argument("--limit",   type=int, default=20,  help="Number of ads per page")
    args = parser.parse_args()
    countries = parse_country_codes(args.country, args.countries)

    today_str = datetime.now().strftime("%Y-%m-%d")
    raw_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), f"../data/raw/tiktok_creative_center/{today_str}")
    )
    os.makedirs(raw_dir, exist_ok=True)

    print("=" * 55)
    print(f"TikTok Top Ads Crawler — {today_str}")
    print(f"Period: {args.period} days | Countries: {', '.join(countries)}")
    print("=" * 55)
    print("[INFO] Capturing API responses from TikTok Creative Center...")

    country_results = []
    for country in countries:
        print("\n" + "-" * 55)
        print(f"[INFO] Crawling country: {country}")
        raw_country_data = crawl_topads(period=args.period, country=country, limit=args.limit)
        country_results.append(raw_country_data)

        country_output_file = write_raw_json(raw_dir, today_str, raw_country_data, country)
        country_s3_key = f"tiktok_creative_center/{today_str}/raw_topads_{today_str}_{country}.json"
        upload_raw_json(country_s3_key, raw_country_data)
        print(f"[INFO] Country raw JSON: {country_output_file}")

    raw_data = country_results[0] if len(country_results) == 1 else combine_country_results(country_results)
    output_file = write_raw_json(raw_dir, today_str, raw_data)
    s3_key = f"tiktok_creative_center/{today_str}/raw_topads_{today_str}.json"
    upload_raw_json(s3_key, raw_data)

    print("\n" + "=" * 55)
    print("Results:")
    total_apis = len(raw_data["all_responses"])
    print(f"Total APIs captured: {total_apis}")

    if raw_data["top_ads_list"]:
        ads_data = raw_data["top_ads_list"].get("data", {})
        ads_list = ads_data.get("materials", ads_data.get("list", []))
        print(f"Top Ads: {len(ads_list)} ads")
        for i, ad in enumerate(ads_list[:3]):
            ad_id   = ad.get("id", "N/A")
            industr = ad.get("industry_key", ad.get("industry", "N/A"))
            country = ad.get("country_code", "N/A")
            print(f"[{i+1}] country={country} | id={ad_id} | industry={industr}")
    else:
        print("Failed to retrieve Top Ads list")

    if raw_data["filters"]:
        print(f"Filters: successfully retrieved")
    else:
        print("Failed to retrieve filters")

    print(f"\nRaw JSON: {output_file}")
    print("=" * 55)


if __name__ == "__main__":
    main()

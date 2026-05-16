import json
import re

nb_path = "/Users/David.Thomas/Library/CloudStorage/OneDrive-Havas/Desktop/ColabCode/CombinedRadarScan.ipynb"
out_path = "/Users/David.Thomas/Library/CloudStorage/OneDrive-Havas/Desktop/ColabCode/CombinedRadarScan_Batch.ipynb"

with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

new_execute_radars_task = """def execute_radars_task(task_name, df_input, client, storage_client):
    import urllib.request
    print(f"\\n{'='*40}\\nProcessing Task: {task_name} (BATCH)\\n{'='*40}")

    df = initialize_dataframe(task_name)
    all_responses = []

    # 1. Prepare Batch Requests
    requests = []
    for idx, row in df_input.iterrows():
        question = get_question_radars(task_name, row['brand'], row['category'], row['market'])
        requests.append({
            'custom_id': str(idx),
            'contents': [{'role': 'user', 'parts': [{'text': question}]}]
        })

    print(f"Submitting {len(requests)} requests to Batch API...")
    batch_job = client.batches.create(
        model=MODELNAME,
        requests=requests
    )
    print(f"Batch job {batch_job.name} started.")

    # 2. Wait for Completion
    while True:
        job = client.batches.get(name=batch_job.name)
        if job.state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        print(f"[{datetime.now().isoformat()}] Job state: {job.state}, sleeping 30s...")
        time.sleep(30)

    if job.state != 'SUCCEEDED':
        print(f"Batch job failed or cancelled. Final state: {job.state}")
        return

    print("Job succeeded! Fetching and parsing results...")

    # 3. Fetch Output
    req = urllib.request.Request(job.output_uri)
    try:
        with urllib.request.urlopen(req) as response:
            lines = response.read().decode('utf-8').strip().split('\\n')
    except Exception as e:
        print(f"Failed to fetch output_uri directly: {e}, falling back to auth...")
        req.add_header('Authorization', f'Bearer {access_secret_version(PROJECT_ID, SECRET_ID)}')
        with urllib.request.urlopen(req) as response:
             lines = response.read().decode('utf-8').strip().split('\\n')

    # map outputs by custom_id
    results_map = {}
    for line in lines:
        if not line.strip(): continue
        res = json.loads(line)
        custom_id = int(res.get('custom_id', -1))
        
        resp_text = None
        try:
            if 'response' in res and 'candidates' in res['response'] and len(res['response']['candidates']) > 0:
                resp_text = res['response']['candidates'][0]['content']['parts'][0]['text']
        except KeyError:
            pass
            
        results_map[custom_id] = resp_text

    # 4. Build DataFrame
    for idx, row in df_input.iterrows():
        resp_text = results_map.get(idx)
        question = get_question_radars(task_name, row['brand'], row['category'], row['market'])

        brand_json = extract_json_robust(resp_text) if resp_text else None

        row_template = {
            "Brand": brand_json.get('brand', row['brand']) if brand_json else row['brand'],
            "Category": row['category'],
            "Market": row['market'],
            "date": pd.Timestamp.now().normalize()
        }
        if task_name == 'CultureConverts':
            row_template["projectname"] = REPORTNAME

        row_data = extract_values_to_row(task_name, brand_json, row_template)
        df = pd.concat([df, pd.DataFrame([row_data])], ignore_index=True)

        all_responses.append({
            "timestamp": datetime.now().isoformat(),
            "brand": row['brand'],
            "market": row['market'],
            "input_question": question,
            "gemini_response": resp_text,
            "success": bool(brand_json)
        })

    df['projectname'] = REPORTNAME

    if task_name == 'CultureConverts':
        print("Adding calculated fields for CultureConverts task...")
        with pd.option_context("future.no_silent_downcasting", True):
            df['Buzzscore'] = (df['Buzz1'] + df['Buzz2'] + df['Buzz3'] + df['Buzz4'] + df['Buzz5']) / 5
            df['Belongscore'] = (df['Belong1'] + df['Belong2'] + df['Belong3'] + df['Belong4'] + (100 - df['Belong5'])) / 5
            df['Beliefscore'] = (df['Belief1'] + df['Belief2'] + df['Belief3'] + df['Belief4'] + (100 - df['Belief5'])) / 5
            df['Behavescore'] = (df['Behave1'] + df['Behave2'] + df['Behave3'] + df['Behave4'] + df['Behave5']) / 5
            df['CultureScore'] = (df['Buzzscore'] + df['Belongscore'] + df['Beliefscore'] + df['Behavescore']) / 4

    export_results(task_name, df, storage_client, all_responses)

def execute_connects_task(df_input, client, storage_client):
    import urllib.request
    print(f"\\n{'='*40}\\nProcessing Task: CultureConnects (BATCH)\\n{'='*40}")

    df = setscandf()
    all_responses = []

    # 1. Prepare Batch Requests
    requests = []
    req_meta = {}
    req_idx = 0
    for idx, row in df_input.iterrows():
        for _, rowss in DFSUPERSPACE.iterrows():
            superspace = rowss["superspace"]
            question = get_question_connects(row["market"], row["audience"], rowss["activities"])
            
            requests.append({
                'custom_id': str(req_idx),
                'contents': [{'role': 'user', 'parts': [{'text': question}]}]
            })
            req_meta[str(req_idx)] = {
                'market': row["market"],
                'audience': row["audience"],
                'superspace': superspace,
                'question': question
            }
            req_idx += 1

    print(f"Submitting {len(requests)} requests to Batch API for CultureConnects...")
    batch_job = client.batches.create(
        model=MODELNAME,
        requests=requests
    )
    print(f"Batch job {batch_job.name} started.")

    # 2. Wait for Completion
    while True:
        job = client.batches.get(name=batch_job.name)
        if job.state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        print(f"[{datetime.now().isoformat()}] Job state: {job.state}, sleeping 30s...")
        time.sleep(30)

    if job.state != 'SUCCEEDED':
        print(f"Batch job failed or cancelled. Final state: {job.state}")
        return

    print("Job succeeded! Fetching and parsing results...")

    # 3. Fetch Output
    req = urllib.request.Request(job.output_uri)
    try:
        with urllib.request.urlopen(req) as response:
            lines = response.read().decode('utf-8').strip().split('\\n')
    except Exception as e:
        print(f"Failed to fetch output_uri directly: {e}")
        req.add_header('Authorization', f'Bearer {access_secret_version(PROJECT_ID, SECRET_ID)}')
        with urllib.request.urlopen(req) as response:
             lines = response.read().decode('utf-8').strip().split('\\n')

    # map outputs by custom_id
    results_map = {}
    for line in lines:
        if not line.strip(): continue
        res = json.loads(line)
        custom_id = str(res.get('custom_id', ''))
        
        resp_text = None
        try:
            if 'response' in res and 'candidates' in res['response'] and len(res['response']['candidates']) > 0:
                resp_text = res['response']['candidates'][0]['content']['parts'][0]['text']
        except KeyError:
            pass
            
        results_map[custom_id] = resp_text

    # 4. Build DataFrame
    for custom_id, meta in req_meta.items():
        resp_text = results_map.get(custom_id)
        
        df = add_to_dataframescan(df, meta['market'], meta['audience'], meta['superspace'], resp_text)

        all_responses.append({
            "timestamp":       datetime.now().isoformat(),
            "market":          meta['market'],
            "audience":        meta['audience'],
            "superspace":      meta['superspace'],
            "input_question":  meta['question'],
            "gemini_response": resp_text,
            "success":         extract_json_robust(resp_text) is not None,
        })

    export_results('CultureConnects', df, storage_client, all_responses)
"""

for cell in nb.get("cells", []):
    if cell.get("cell_type") == "code":
        src = "".join(cell.get("source", []))
        if "def execute_radars_task" in src:
            # Replace the entire cell source with our new logic
            cell["source"] = [line + "\\n" for line in new_execute_radars_task.split("\\n")]
            cell["source"][-1] = cell["source"][-1].rstrip("\\n") # Remove trailing newline from last element

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=2)

print(f"Created {out_path}")

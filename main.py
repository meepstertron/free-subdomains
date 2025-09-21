from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import os
from dotenv import load_dotenv
import hackdb 
from hackdb import HackDB
import cloudflare
from cloudflare import Cloudflare


load_dotenv()

APPROVAL_CHANNEL = "C08S3FC6WTE"  

hackdb = HackDB(token="hkdb_tkn_b4eb716d-3eb8-4126-b5f0-eb1a4598aca2")

client = Cloudflare(
    api_token=os.environ.get("CLOUDFLARE_API_TOKEN"),  
)


app = App(token=os.getenv("SLACK_BOT_TOKEN"))

@app.command("/available_domains")
def handle_available_domains_command(ack, respond, command):
    # Acknowledge the command request
    ack()
    
    domains = hackdb.domains.find_many()
    respond("Here are the silly domains where you currently can get a subdomain:\n" + "\n- ".join([domain['root'] for domain in domains]))
    

@app.command("/get_subdomain")
def handle_get_subdomain_command(ack, body, client):
    # Acknowledge the command request
    ack()
    
    domains = hackdb.domains.find_many()

    

    
    
    try:
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
	"type": "modal",
    "callback_id": "subdomain_modal",
	"submit": {
		"type": "plain_text",
		"text": "YES, i affirm :3",
		"emoji": True
	},
	"close": {
		"type": "plain_text",
		"text": "i dont want a domain :(",
		"emoji": True
	},
	"title": {
		"type": "plain_text",
		"text": "SILLY subDOMAIN REGISTAR",
		"emoji": True
	},
	"blocks": [
		{
			"type": "section",
			"text": {
				"type": "plain_text",
				"text": "So you want a silly domain eh?",
				"emoji": True
			}
		},
		{
			"type": "input",
			"block_id": "subdomain_block",
			"element": {
				"type": "plain_text_input",
				"action_id": "subdomain_input"
			},
			"label": {
				"type": "plain_text",
				"text": "Your subdomain name:",
				"emoji": True
			}
		},
		{
			"type": "input",
			"block_id": "root_block",
			"element": {
				"type": "static_select",
				"placeholder": {
					"type": "plain_text",
					"text": "Select a Root Domain",
					"emoji": True
				},
				"options": [
                    {
                        "text": {
                            "type": "plain_text",
                            "text": domain["root"],
                            "emoji": True
                        },
                        "value": str(domain["id"])
                    } for domain in domains
				],
				"action_id": "root_select"
			},
			"label": {
				"type": "plain_text",
				"text": "What silly do you fancy",
				"emoji": True
			}
		},
		{
			"type": "divider"
		},
		{
			"type": "section",
			"text": {
				"type": "plain_text",
				"text": "Onto the details",
				"emoji": True
			}
		},
		{
			"type": "input",
			"block_id": "dns_block",
			"element": {
				"type": "static_select",
				"placeholder": {
					"type": "plain_text",
					"text": "Select an DNS Record Type",
					"emoji": True
				},
				"options": [
					{
						"text": {
							"type": "plain_text",
							"text": "A",
							"emoji": True
						},
						"value": "A"
					},
					{
						"text": {
							"type": "plain_text",
							"text": "AAAA",
							"emoji": True
						},
						"value": "AAAA"
					},
					{
						"text": {
							"type": "plain_text",
							"text": "CNAME",
							"emoji": True
						},
						"value": "cname"
					}
				],
				"action_id": "dns_select"
			},
			"label": {
				"type": "plain_text",
				"text": "DNS Record",
				"emoji": True
			}
		},
		{
			"type": "input",
			"block_id": "target_block",
			"element": {
				"type": "plain_text_input",
				"action_id": "target_input"
			},
			"label": {
				"type": "plain_text",
				"text": "Target (where you wana point)",
				"emoji": True
			}
		},
		{
			"type": "divider"
		},
		{
			"type": "section",
			"text": {
				"type": "plain_text",
				"text": "By affirming you want this really cool domain name you agree to not do bad shit and agree that i may take down your subdomain if you are a bad boy!!",
				"emoji": True
			}
		}
	]
}
        )
    except Exception as e:
        print(f"Error opening modal: {e}")



@app.view("subdomain_modal")
def handle_view_submission_events(ack, body, logger):
    ack()
    
    
    if body["view"]["title"]["text"] == "SILLY subDOMAIN REGISTAR":
        
        values = body["view"]["state"]["values"]
        
        
        subdomain_name = values["subdomain_block"]["subdomain_input"]["value"]
        root_domain = values["root_block"]["root_select"]["selected_option"]["value"]
        dns_type = values["dns_block"]["dns_select"]["selected_option"]["value"]
        target = values["target_block"]["target_input"]["value"]
        
        
        logger.info(f"Subdomain: {subdomain_name}, Root: {root_domain}, DNS: {dns_type}, Target: {target}")
        
        root_domain_record = hackdb.domains.find_many(where={"id": {"equals": int(root_domain)}})
        if not root_domain_record:
            logger.error(f"Root domain with ID {root_domain} not found.")
            return
        root_domain_record = root_domain_record[0]
        
        check_dupes = hackdb.subdomains.find_many(where={"subdomain": {"equals": subdomain_name}, "root_id": {"equals": int(root_domain)}})
        if len(check_dupes) > 0:
            # reply to user that that subdomain already exists via a slack message
            app.client.chat_postMessage(
                channel=body["user"]["id"],
                text=f"Subdomain *{subdomain_name}* already exists under *{root_domain_record['root']}*. sowry :("
            )
            return

        
        subdomain_record = hackdb.subdomains.create({"approved": False, "root_id": int(root_domain), "slack_id": body["user"]["id"], "subdomain": subdomain_name, "type": dns_type.upper(), "target": target})

        if not subdomain_record:
            logger.error("Failed to create subdomain record.")
            return

        
        subdomain_records = hackdb.subdomains.find_many()
        subdomain_id = None
        for record in subdomain_records:
            if record["subdomain"] == subdomain_name and record["root_id"] == root_domain:
                subdomain_id = record["id"]
                break
        if subdomain_id is None:
            logger.error("Failed to retrieve the newly created subdomain record.")
            return
        

        # send message to approval channel
        app.client.chat_postMessage(
            channel=APPROVAL_CHANNEL,
            blocks=[
		{
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": f"<@{body['user']['id']}> has requested the domain name *{subdomain_name}*.{root_domain_record['root']}"
			}
		},
		{
			"type": "actions",
			"elements": [
				{
					"type": "button",
					"text": {
						"type": "plain_text",
						"text": "Approve",
						"emoji": True
					},
					"value": f"approve:{subdomain_id}",
					"action_id": "approve_request"
				},
				{
					"type": "button",
					"text": {
						"type": "plain_text",
						"text": "Send to shadow realm",
						"emoji": True
					},
					"value": f"deny:{subdomain_id}",
					"action_id": "deny_request"
				}
			]
		}
	])
    else:
        logger.info(body)

@app.action("approve_request")
def handle_approve_request(ack, body, logger):
    ack()
    action_value = body["actions"][0]["value"]
    action, subdomain_id_str = action_value.split(":")
    subdomain_id = int(subdomain_id_str)
    # update the subdomain to approved
    
    old_record = hackdb.subdomains.find_many(where={"id": {"equals": subdomain_id}})
    if not old_record:
        logger.error(f"Subdomain with ID {subdomain_id} not found.")
        return
    
    hackdb.subdomains.delete(where={"id": {"equals": subdomain_id}})
    
    hackdb.subdomains.create({"approved": True, "root_id": old_record[0]["root_id"], "slack_id": old_record[0]["slack_id"], "subdomain": old_record[0]["subdomain"], "type": old_record[0]["type"], "target": old_record[0]["target"]})
    
    if old_record[0]["type"] == "A":
        client.dns.records.create(
            zone_id=hackdb.domains.find_many(where={"id": {"equals": old_record[0]["root_id"]}})[0]["zone_id"],
            name=f"{old_record[0]['subdomain']}.{hackdb.domains.find_many(where={'id': {'equals': old_record[0]['root_id']}})[0]['root']}",
            type="A",
            content=old_record[0]["target"],
            ttl=300,
            proxied=False
        )
        
    elif old_record[0]["type"] == "AAAA":
        client.dns.records.create(
            zone_id=hackdb.domains.find_many(where={"id": {"equals": old_record[0]["root_id"]}})[0]["zone_id"],
            name=f"{old_record[0]['subdomain']}.{hackdb.domains.find_many(where={'id': {'equals': old_record[0]['root_id']}})[0]['root']}",
            type="AAAA",
            content=old_record[0]["target"],
            ttl=300
        )
    elif old_record[0]["type"] == "CNAME":
        client.dns.records.create(
            zone_id=hackdb.domains.find_many(where={"id": {"equals": old_record[0]["root_id"]}})[0]["zone_id"],
            name=f"{old_record[0]['subdomain']}.{hackdb.domains.find_many(where={'id': {'equals': old_record[0]['root_id']}})[0]['root']}",
            type="CNAME",
            content=old_record[0]["target"],
            ttl=300
        )
        
    

        
        
    # update the approval message to remove buttons
    app.client.chat_update(
        channel=body["container"]["channel_id"],
        ts=body["container"]["message_ts"],
        text=f"<@{body['user']['id']}> has approved the domain name *{old_record[0]['subdomain']}.{hackdb.domains.find_many(where={'id': {'equals': old_record[0]['root_id']}})[0]['root']}*",
        blocks=[]
    )
    
    # notify the user
    app.client.chat_postMessage(
        channel=old_record[0]["slack_id"],
        text=f"Your subdomain *{old_record[0]['subdomain']}.{hackdb.domains.find_many(where={'id': {'equals': old_record[0]['root_id']}})[0]['root']}* has been approved and is now live! Ouppy is happy :3"
    )
    
    logger.info(f"Request approved for subdomain ID {subdomain_id}!")

@app.action("deny_request")
def handle_deny_request(ack, body, logger):
    ack()
    action_value = body["actions"][0]["value"]
    action, subdomain_id_str = action_value.split(":")
    subdomain_id = int(subdomain_id_str)
    # Delete the request or mark as denied
    old_record = hackdb.subdomains.find_many(where={"id": {"equals": subdomain_id}})
    if not old_record:
        logger.error(f"Subdomain with ID {subdomain_id} not found.")
        return

    hackdb.subdomains.delete(where={"id": {"equals": subdomain_id}})
    logger.info(f"Request denied for subdomain ID {subdomain_id}!")
    
    app.client.chat_update(
        channel=body["container"]["channel_id"],
        ts=body["container"]["message_ts"],
        text=f"<@{body['user']['id']}> has denied the domain name *{old_record[0]['subdomain']}.{hackdb.domains.find_many(where={'id': {'equals': old_record[0]['root_id']}})[0]['root']}*",
        blocks=[]
    )
    
    app.client.chat_postMessage(
        channel=old_record[0]["slack_id"],
        text=f"Your subdomain *{old_record[0]['subdomain']}.{hackdb.domains.find_many(where={'id': {'equals': old_record[0]['root_id']}})[0]['root']}* has been denied. Ouppy is sad :("
    )

if __name__ == "__main__":
    # Use Socket Mode for simplicity (no need for public URL)
    handler = SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN"))
    handler.start()
    
    

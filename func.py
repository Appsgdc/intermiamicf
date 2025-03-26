import requests
import json

url = "https://intermiamiapis.fortressus.com/FGB_WebApplication/InterMiami/Production/api/CRM/ThirdPartyTransactionsPayments"

payload = json.dumps({
  "Header": {
    "Client_AppID": "com.InterMiami",
    "Client_APIKey": "59e24524-f540-4725-95d8-7e428b160c13",
    "Client_AgencyCode": "InterMiami",
    "UniqID": 1
  },
  "FromDateTime": "2024-07-01T00:00:00",
  "ToDateTime": "2024-07-29T23:59:59",
  "PageSize": 1000,
  "PageNumber": 1
})
headers = {
  'x-api-key': 'fcbc1463-ea65-4e56-b4c9-dc09928dde19',
  'Content-Type': 'application/json',
  'Authorization': '••••••',
  'Cookie': 'ARRAffinity=3e817c3557a93ad52921b3a36ef4ffbb8942d9abdae30f61f07fe58cab00d896; ARRAffinitySameSite=3e817c3557a93ad52921b3a36ef4ffbb8942d9abdae30f61f07fe58cab00d896'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)

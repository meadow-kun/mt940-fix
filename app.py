import os
import dotenv
import requests
import mt940
from decimal import Decimal
from datetime import datetime
import sys

# Load the environment variables
dotenv.load_dotenv()

EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY')

# Function to fetch historical exchange rate for a specific date
def fetch_exchange_rate(date, from_currency='SEK', to_currency='EUR'):
    year = date.strftime('%Y')
    month = date.strftime('%m')
    day = date.strftime('%d')
    url = f'https://v6.exchangerate-api.com/v6/{EXCHANGE_API_KEY}/history/{from_currency}/{year}/{month}/{day}'
    response = requests.get(url)
    print(f"API Response: {response.text}")

    try:
        data = response.json()
        if 'conversion_rates' in data and to_currency in data['conversion_rates']:
            return Decimal(data['conversion_rates'][to_currency])
        else:
            raise ValueError(f"Unexpected API response format: {data}")
    except ValueError as e:
        print(f"Error parsing JSON response: {e}")
        return None

# Function to convert amount from SEK to EUR using the exchange rate
def convert_amount(amount, exchange_rate):
    return (amount * exchange_rate).quantize(Decimal('0.01'))

# Function to convert MT940 transactions from SEK to EUR
def convert_mt940(file_path, output_path):
    with open(file_path, 'r') as file:
        original_lines = file.readlines()

    transactions = mt940.parse(file_path)
    converted_lines = []
    transaction_index = 0

    for line in original_lines:
        if line.startswith(':60F:'):
            # Change the currency and amount in the opening balance line
            parts = line.split('SEK')
            if len(parts) > 1:
                balance_parts = parts[1].split(',')
                original_amount = Decimal(balance_parts[0].replace(',', '.'))
                # Use the first transaction date for opening balance exchange rate
                exchange_rate = fetch_exchange_rate(transactions[0].data['date'])
                converted_amount = convert_amount(original_amount, exchange_rate)
                line = f"{parts[0]}EUR{converted_amount:.2f}\n"

        elif line.startswith(':62F:'):
            # Change the currency and amount in the closing balance line
            parts = line.split('SEK')
            if len(parts) > 1:
                balance_parts = parts[1].split(',')
                original_amount = Decimal(balance_parts[0].replace(',', '.'))
                # Use the last transaction date for closing balance exchange rate
                exchange_rate = fetch_exchange_rate(transactions[-1].data['date'])
                converted_amount = convert_amount(original_amount, exchange_rate)
                line = f"{parts[0]}EUR{converted_amount:.2f}\n"

        elif line.startswith(':25:'):
            # Change the currency in the account identification line
            line = line.replace('SEK', 'EUR')

        elif line.startswith(':61:'):
            transaction = transactions[transaction_index]
            transaction_index += 1

            date = transaction.data['date']
            amount = transaction.data['amount'].amount
            funds_code = 'C' if amount >= 0 else 'D'
            transaction_code = transaction.data.get('id', 'NMSC')
            customer_reference = transaction.data.get('customer_reference', 'NONREF')

            # Fetch exchange rate for the transaction date
            exchange_rate = fetch_exchange_rate(date)
            # Convert the amount
            converted_amount = convert_amount(amount, exchange_rate)
            line = f":61:{date.strftime('%y%m%d')}{funds_code}{abs(converted_amount):.2f}N{transaction_code}{customer_reference}\n"
        
        elif line.startswith(':86:'):
            transaction_details = transaction.data.get('transaction_details', '')
            line = f":86:{transaction_details}\n"

        converted_lines.append(line)

    with open(output_path, 'w') as output_file:
        output_file.writelines(converted_lines)
        

# Function to count the number of transactions in an MT940 statement
def count_transactions(file_path):
    import mt940
    transactions = mt940.parse(file_path)
    return len(transactions)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Please provide the path to the MT940 file as an argument')
        sys.exit(1)

    input_file_path = sys.argv[1]

    if '--count' in sys.argv:
        transaction_count = count_transactions(input_file_path)
        print(f'The number of transactions in the statement: {transaction_count}')
    else:
        output_file_path = f'converted_{os.path.basename(input_file_path)}'
        convert_mt940(input_file_path, output_file_path)
        print(f'Converted file saved to {output_file_path}')

        # Read and compare original and converted files
        def read_file(file_path):
            with open(file_path, 'r') as file:
                return file.read()

        original_content = read_file(input_file_path)
        converted_content = read_file(output_file_path)

        print("\nOriginal File Content:")
        print(original_content)

        print("\nConverted File Content:")
        print(converted_content)
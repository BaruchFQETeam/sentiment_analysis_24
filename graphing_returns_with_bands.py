import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import time
from Robinhood.RobhinhoodQuotes import write_sp500_data
from Robinhood.sdp import get_optimal_weights

#seaborn is a library for making statistical graphics in Python. It is built on top of matplotlib and closely integrated with pandas data structures.

tickers = None

def load_data(file_path: str) -> None:
    global tickers
    df = pd.read_csv(file_path)
    df = df.set_index('Date')
    df.index = pd.to_datetime(df.index).strftime('%Y-%m-%d')
    tickers = df.columns


def calculate_portfolio_value_no_rebalancing(df, weights, initial_investment=1000):
    """
    Calculate portfolio value with initial weights, allowing the weights to drift over time.
    This does not assume daily rebalancing.
    
    Returns:
    - pd.Series: Series of portfolio values over time.
    """
    # Calculate initial investment distribution per stock
    initial_investment_per_stock = {
        stock: initial_investment * weight for stock, weight in weights.items() if stock in df.columns
    }
    
    # Calculate portfolio value by allowing weights to drift over time
    portfolio_values = []
    for date, prices in df.iterrows():
        portfolio_value = sum(prices[stock] * (initial_investment_per_stock[stock] / df[stock].iloc[0]) for stock in initial_investment_per_stock)
        portfolio_values.append(portfolio_value)
    
    return pd.Series(portfolio_values, index=df.index)


def calculate_portfolio_value_with_rebalancing(df, weights, initial_investment=1000, rebalance_frequency=1):
    """
    Calculate portfolio value with periodic rebalancing.
    
    Args:
    - df (pd.DataFrame): DataFrame with Date as the index and stock prices as columns.
    - weights (dict): Dictionary with stock tickers as keys and weights as values.
    - initial_investment (float): Starting amount to invest in the portfolio.
    - rebalance_frequency (int): Number of days between rebalancing. If set to 0, no rebalancing occurs.
    
    Returns:
    - pd.Series: Series of portfolio values over time.
    """
    portfolio_values = []
    initial_investment_per_stock = {stock: initial_investment * weight for stock, weight in weights.items() if stock in df.columns}
    
    # Initial shares bought based on initial weights and first day's prices
    shares = {stock: initial_investment_per_stock[stock] / df[stock].iloc[0] for stock in initial_investment_per_stock}
    
    for i, (date, prices) in enumerate(df.iterrows()):
        # Calculate current portfolio value
        portfolio_value = sum(prices[stock] * shares[stock] for stock in shares)
        portfolio_values.append(portfolio_value)
        
        # Rebalance if needed (based on frequency) and not on the first date
        if rebalance_frequency > 0 and i % rebalance_frequency == 0 and i != 0:
            # Rebalance portfolio: calculate new investment per stock based on current portfolio value
            new_investment_per_stock = {stock: portfolio_value * weight for stock, weight in weights.items()}
            shares = {stock: new_investment_per_stock[stock] / prices[stock] for stock in new_investment_per_stock}
    
    return pd.Series(portfolio_values, index=df.index)


def add_ewma_bollinger_bands(portfolio_values, halflife_days):
    """
    Add EWMA and Bollinger Bands to the portfolio values.
    """
    df = pd.DataFrame({'portfolio_value': portfolio_values})
    
    # Calculate EWMA
    df['ewma'] = df['portfolio_value'].ewm(halflife=halflife_days).mean()
    
    # Calculate standard deviation and Bollinger Bands
    df['std_dev'] = df['portfolio_value'].rolling(window=halflife_days).std()
    df['bollinger_upper'] = df['ewma'] + (2 * df['std_dev'])
    df['bollinger_lower'] = df['ewma'] - (2 * df['std_dev'])
    
    df.drop(columns=['std_dev'], inplace=True)
    return df


# Test code
def index_compiler(weights_dict: dict, title: str, halflife_days: int = 20, initial_investment=1000, rebalance=True, rebalance_frequency=1) -> tuple:
    """
    Parameters:
    - weights_dict: Dictionary of stock tickers and their weights.
    - title: Title of the portfolio.
    - halflife_days: Halflife in days for the EWMA calculation.
    - initial_investment: Initial investment amount.
    - rebalance: Boolean flag for rebalancing.
    - rebalance_frequency: Frequency of rebalancing in days.
        - 5 days for weekly rebalancing. Since the market is open 5 days a week.
        - Default is daily rebalancing.

    Computes portfolio value and adds EWMA and Bollinger Bands.

    Returns a tuple of the DataFrame with EWMA and Bollinger Bands, the weights dictionary, and the title.
    """
    df = pd.read_csv('StockPortfolio_5year_close_prices.csv')
    df = df.set_index('Date')
    df.index = pd.to_datetime(df.index).strftime('%Y-%m-%d')

    # Validate that weights sum to 1
    total_weight = sum(weights_dict.values())
    if total_weight != 1:
        weights_dict = {ticker: weight / total_weight for ticker, weight in weights_dict.items()}

    if rebalance:
        portfolio_values = calculate_portfolio_value_with_rebalancing(df, weights_dict, initial_investment, rebalance_frequency)
    else:
        portfolio_values = calculate_portfolio_value_no_rebalancing(df, weights_dict, initial_investment)

    ewma_bollinger_df = add_ewma_bollinger_bands(portfolio_values, halflife_days)
    return ewma_bollinger_df, weights_dict, title


def plot_returns(returns_n_weights, trade_logs=None, trades_tally=0):
    """
    Parameters: 
    - returns_n_weights: A list of tuples with DataFrame, weights, and title as returned by index_compiler.
    - trade_logs: List of tuples with (trade_date, trade_price, trade_type, total_trade_pnl).
    
    Plots portfolio values, EWMA, Bollinger Bands, and cumulative PnL from trade_logs, with trade markers on the PnL tracker.
    """
    plt.figure(figsize=(12, 7))

    labeled_bands = False
    cumulative_pnl = []  # To store cumulative PnL over time
    pnl_dates = []

    for ewma_bollinger_df, weights, title in returns_n_weights:
        if title == "SPY":
            # Only plot the portfolio value for SPY
            plt.plot(ewma_bollinger_df.index, ewma_bollinger_df['portfolio_value'], 
                    label=f"S&P Index (SPY)", linestyle='-', linewidth=2, color='black', alpha=0.8)
        else:
            # Plot the Bollinger Bands, EWMA, and Portfolio Value for other titles
            if not labeled_bands:
                plt.fill_between(ewma_bollinger_df.index, ewma_bollinger_df['bollinger_upper'], 
                                ewma_bollinger_df['bollinger_lower'], color='gray', alpha=0.2, 
                                label=f"Bollinger Bands Range")
                plt.plot(ewma_bollinger_df.index, ewma_bollinger_df['bollinger_upper'], color='green', linestyle=':', label="Upper Band")
                plt.plot(ewma_bollinger_df.index, ewma_bollinger_df['bollinger_lower'], color='red', linestyle=':', label="Lower Band")
                labeled_bands = True
            else:
                plt.fill_between(ewma_bollinger_df.index, ewma_bollinger_df['bollinger_upper'], 
                                ewma_bollinger_df['bollinger_lower'], color='gray', alpha=0.2)
                plt.plot(ewma_bollinger_df.index, ewma_bollinger_df['bollinger_upper'], color='green', linestyle=':')
                plt.plot(ewma_bollinger_df.index, ewma_bollinger_df['bollinger_lower'], color='red', linestyle=':')

            plt.plot(ewma_bollinger_df.index, ewma_bollinger_df['portfolio_value'], 
                    label=f"{title} Portfolio Value")
            plt.plot(ewma_bollinger_df.index, ewma_bollinger_df['ewma'], 
                    label=f"{title} EWMA", linestyle='--')


    # Add trade points and PnL line if available
    if trade_logs:
        # Extract cumulative PnL directly from trade logs
        for trade_date, trade_price, trade_type, total_trade_pnl in trade_logs:
            pnl_dates.append(trade_date)
            cumulative_pnl.append(total_trade_pnl)

        # Plot the PnL line
        plt.plot(pnl_dates, cumulative_pnl, label="Our Mean Reversion Trades Cumulative PnL", color='grey', linewidth=2)

        # Plot trade markers on the PnL tracker
        used_labels = set()  # Track used labels for legend only
        for trade_date, trade_price, trade_type, total_trade_pnl in trade_logs:
            if trade_type == 'long_entry':
                plt.scatter(trade_date, total_trade_pnl, color='blue', marker='^', s=50, 
                            label='Open Long' if 'Open Long' not in used_labels else "", alpha=0.8, zorder=5)
                used_labels.add('Open Long')
            elif trade_type == 'long_exit':
                plt.scatter(trade_date, total_trade_pnl, color='orange', marker='v', s=50, 
                            label='Close Long' if 'Close Long' not in used_labels else "", alpha=0.8, zorder=5)
                used_labels.add('Close Long')
            elif trade_type == 'short_entry':
                plt.scatter(trade_date, total_trade_pnl, color='green', marker='^', s=50, 
                            label='Open Short' if 'Open Short' not in used_labels else "", alpha=0.8, zorder=5)
                used_labels.add('Open Short')
            elif trade_type == 'short_exit':
                plt.scatter(trade_date, total_trade_pnl, color='red', marker='v', s=50, 
                            label='Close Short' if 'Close Short' not in used_labels else "", alpha=0.8, zorder=5)
                used_labels.add('Close Short')
            

    plt.title("Cumulative PnL with Trades")
    plt.xlabel("Date")
    plt.ylabel("PnL ($)")
    plt.xticks(ticks=range(0, len(pnl_dates), max(1, len(pnl_dates) // 10)), rotation=45)
    weights_dict = returns_n_weights[0][1] # Get the weights of the portfolio
    weights_list = [f"{ticker}: {weight:.2%}" for ticker, weight in weights_dict.items()]  # Format each stock weight
    weights_text = "\n".join(weights_list)  # Combine into a multi-line string

    # Add legend
    plt.legend(loc='upper left')

    # Add weights and total trades as additional text, 1 weight per line
    plt.text(1.02, 0.5, f"Stock Weights:\n{weights_text}\n\nTotal Trades: {trades_tally}", 
            transform=plt.gca().transAxes, fontsize=10, verticalalignment='center', 
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.5))

    plt.grid(True)
    plt.tight_layout()
    plt.show()




def csv_weighted_portfolio(file_path: str, weights ,halflife_days: int = 20, initial_investment=1000) -> None:
    """
    Creates an equally weighted portfolio based on the CSV and plots its value with EWMA and Bollinger Bands.
    """
    global tickers
    load_data(file_path)
    tickers_adjusted = tickers.tolist()  # Convert Index to a list
    tickers_adjusted.remove('SPY')      # Remove 'SPY' from the list
    #equal_weights = {ticker: 1/len(tickers_adjusted) for ticker in tickers_adjusted}
    equal_weights = weights # this mf is a diciotnary
    print(f"Weights: {equal_weights}")
    equal_portfolio_rebalanced = index_compiler(equal_weights, 'Equally Weighted Portfolio (Rebalanced Daily)', halflife_days, initial_investment, rebalance=True, rebalance_frequency=1)
    equal_portfolio_no_rebalancing = index_compiler(equal_weights, 'Equally Weighted Portfolio (No Rebalancing)', halflife_days, initial_investment, rebalance=False,)
    equal_portfolio_rebalanced_weekly = index_compiler(equal_weights, 'Equally Weighted Portfolio (Rebalanced Weekly)', halflife_days, initial_investment, rebalance=True, rebalance_frequency=5)
    return [equal_portfolio_rebalanced_weekly]

    # plot_returns([equal_portfolio_rebalanced])


def individual_stock_prep_plot(tickers_recieved, halflife_days: int = 20, initial_investment=1000) -> None:
    """
    Creates a portfolio for each stock in the csv and plots its value with EWMA and Bollinger Bands.

    """
    #specific ticker plot data
    ticker_data = []
    for ticker in tickers_recieved:
        indv_dict = {ticker: 1}
        ind_stock_data = index_compiler(indv_dict, f'{ticker}', halflife_days, initial_investment, rebalance=True)
        ticker_data.append(ind_stock_data)
    return ticker_data


def track_trades(df, initial_investment=1000):
    """
    Parameters:
    - df: DataFrame with the date as the index and portfolio values, EWMA, and Bollinger Bands as columns.
    - portfolio_start_val: Initial investment amount.

    Returns a tuple of trade logs and the total number of trades.
    trade_logs is a list of tuples with (trade_date, trade_price, trade_type, total_trade_pnl).
    trades_tally is an integer representing the total number of trades.
    """
    current_position = None
    entry_price = 0
    realized_balance = initial_investment  # Start with initial investment
    unrealized_pnl = 0
    trades_tally = 0

    # Ensure these columns exist in your DataFrame
    df['trade_pnl'] = 0.0
    df['total_trade_pnl'] = 0.0
    df['position'] = None

    # Lists for tracking trades
    trade_logs = []  # Log of all trades for plotting
    df.loc[df.index[0], 'total_trade_pnl'] = realized_balance
    trade_logs.append((df.index[0], df.loc[df.index[0], 'portfolio_value'], 'neither', realized_balance))
    for i in range(1,len(df)):
        price = df.loc[df.index[i], 'portfolio_value']
        ewma = df.loc[df.index[i], 'ewma']
        upper = df.loc[df.index[i], 'bollinger_upper']
        lower = df.loc[df.index[i], 'bollinger_lower']

        if i > 0:
            # Carry forward the previous total_trade_pnl
            df.loc[df.index[i], 'total_trade_pnl'] = df.loc[df.index[i - 1], 'total_trade_pnl']

        else:
            # Initialize for the first row
            df.loc[df.index[i], 'total_trade_pnl'] = 0

        # Calculate unrealized PnL if a position is open
        if current_position == 'short':
            unrealized_pnl = realized_balance * (entry_price - price) / entry_price
        elif current_position == 'long':
            unrealized_pnl = realized_balance * (price - entry_price) / entry_price
        else:
            unrealized_pnl = 0

        # Append to trade_logs
        trade_logs.append((df.index[i], price, 'neither', df.loc[df.index[i], 'total_trade_pnl'] + unrealized_pnl))

        # Enter a short position
        if current_position is None and price > upper:
            print(f"Short position entered at {price}")
            current_position = 'short'
            entry_price = price
            df.loc[df.index[i], 'position'] = 'short'

            # Calculate units traded (all-in on realized balance)
            units_traded = realized_balance / entry_price
            trade_logs[i] = (trade_logs[i][0], trade_logs[i][1], 'short_entry', trade_logs[i][3])

        # Enter a long position
        elif current_position is None and price < lower:
            print(f"Long position entered at {price}")
            current_position = 'long'
            entry_price = price
            df.loc[df.index[i], 'position'] = 'long'

            # Calculate units traded (all-in on realized balance)
            units_traded = realized_balance / entry_price
            trade_logs[i] = (trade_logs[i][0], trade_logs[i][1], 'long_entry', trade_logs[i][3])

        # Exit short position
        elif current_position == 'short' and price < ewma:
            print(f"Short position exited at {price}")
            pnl = units_traded * (entry_price - price)  # Profit from price decrease
            realized_balance += pnl  # Update realized balance
            df.loc[df.index[i], 'total_trade_pnl'] += pnl
            current_position = None
            trades_tally += 1
            trade_logs[i] = (trade_logs[i][0], trade_logs[i][1], 'short_exit', df.loc[df.index[i], 'total_trade_pnl'])

        # Exit long position
        elif current_position == 'long' and price > ewma:
            print(f"Long position exited at {price}")
            pnl = units_traded * (price - entry_price)  # Profit from price increase
            realized_balance += pnl  # Update realized balance
            df.loc[df.index[i], 'total_trade_pnl'] += pnl
            current_position = None
            trades_tally += 1
            trade_logs[i] = (trade_logs[i][0], trade_logs[i][1], 'long_exit', df.loc[df.index[i], 'total_trade_pnl'])

    print(df[['portfolio_value', 'position', 'total_trade_pnl']])

    # Debug output
    print("Total Trades:", trades_tally)
    print("Final Realized Balance:", realized_balance)
    if current_position == 'Open':
        print("Position still open, This means the graph ends with an open position")

    return trade_logs, trades_tally

#pick stocks to use 

stock_picks = [ 'SRPT']
# some russell 2000 stocks
stock_picks = [
    "FTAI", "SFM", "INSM", "PCVX", "AIT", "FLR", "CRDO", "CRS", "FN", "MLI", "RKLB", "SSB", "HQY", "GTLS", "UFPI",
    "ENSG", "RVMD", "CVLT", "ANF", "IONQ", "AUR", "ONB", "MOD", "EXLS", "MARA", "SPXC", "SPSC", "CMC", "TMHC", "BECN",
    "LUMN", "RHP", "HLNE", "GKOS", "CSWI", "CWST", "GBCI", "QTWO", "BMI", "HRI", "HIMS", "MTH", "RMBS", "COOP", "SUM"
    , "SIGI", "LNTH", "KNF", "ALTR", "BPMC", "UPST", "HALO", "ESNT", "ACIW", "HOMB", "MMSI", "STRL", "PIPR",
    "NOVT", "KRG", "JXN", "WTS", "FSS", "BCC", "CYTK", "ZWS", "EAT", "UMBF", "QLYS", "EPRT", "CBT", "GATX", "BCPC",
    "GPI", "ALTM", "TRNO", "MDGL", "SKY", "CHX", "VRNS", "DY", "CNX", "FFIN", "RDNT", "RDN", "BE", "UBSI",
    "MAC", "ITRI", "KBH", "SLG", "CWAN", "SHAK", "ABG", "NXT", "ACA", "MATX", "WK", "CADE", "CRNX", "IBP", "ALKS",
    "BIPC", "HWC", "VLY", "TENB", "IDCC", "KTB", "BDC", "CORT", "PRMB", "NJR", "PECO", "EXPO", "FELE", "IRT", "KAI",
    "SFBS", "TGTX", "LRN", "POR", "ZETA", "ITGR", "SM", "AVNT", "CTRE", "SWX", "FTDR", "KRYS", "BOOT", "NSIT", "BOX",
    "PRIM", "PLXS", "MUR", "ADMA", "SKYW", "FUN", "MGY", "MMS", "TXNM", "SOUN", "GVA", "ROAD", "AEIS", "BKH", "NE",
    "GH", "ASB", "SBRA", "SMTC", "SITM", "AVAV", "ORA", "SANM", "ABCB", "ESGR", "BCO", "MHO", "AROC", "TCBI", "FCFS",
    "GLNG", "CVCO", "WHD", "SG", "PBH", "RNA", "FUL", "KTOS", "CNO", "CALM", "ASGN", "OGS", "HAE", "NPO", "PRCT",
    "BBIO", "SR", "IBOC", "AX", "NOG", "REZI", "PJT", "SIG", "VRRM", "GMS", "MWA", "CNK", "OPCH", "SKT", "MC", "JBT",
    "STEP", "RXO", "KFY", "RUSHA", "TPH", "PI", "APLE", "VSCO", "CBZ", "ALE", "ENS", "SLAB", "ABM", "WDFC", "RIOT",
    "BL", "ESE", "CDP", "CRC", "ACLX", "PTCT", "MGEE", "AXSM", "WD", "DORM", "EBC", "MIR", "TEX", "HASI", "PCH", "ASO",
    "SMPL", "POWI", "ATMU", "GEO", "JOBY", "LANC", "AGIO", "UCB", "AI", "ATGE", "CEIX", "FRSH", "CCOI", "TDS",
    "PTON", "VCYT", "CARG", "UEC", "ASTS", "BHVN", "BNL", "BXMT", "ICUI", "ATKR", "ACVA", "HP", "TGNA", "BLKB", "HCC",
    "NWE", "ALRM", "NUVL", "SXT", "AEO", "AUB", "FORM", "SLVM", "NHI", "HL", "SHOO", "RYTM", "NMIH", "BWIN", "OTTR",
    "HGV", "RELY", "URBN", "PBF", "GHC", "HUBG", "ALIT", "SYNA", "OSCR", "FULT", "TRN", "CRVL", "VERX", "DNLI", "CBU",
    "GFF", "IIPR", "AWR", "TWST", "CVBF", "PATK", "PTEN", "WSFS", "FLG", "CORZ", "TNET", "HTLF", "AGYS", "SRRK", "PFSI",
    "LCII", "NSP", "HBI", "MGRC", "AVA", "UNF", "NVCR", "SNEX", "OSIS", "RIG", "PRGS", "SATS", "VCTR", "GT", "CNS",
    "GSHD", "OUT", "IOSP", "FIBK", "PAR", "CPK", "SWTX", "FOLD", "BTU", "UE", "PRK", "CATY", "ARWR", "CWT", "AZZ",
    "NEOG", "LBRT", "PLMR", "HNI", "DIOD", "BRZE", "MYRG", "APAM", "BGC", "AKR", "OII", "VCEL", "TOWN", "ARCH", "PAYO",
    "SFNC", "COMP", "DRS", "ENR", "AMBA", "FCPT", "LIVN", "NARI", "BUR", "FBP", "STNE", "RPD", "ENVA", "SDRL", "BANF",
    "INDB", "LXP", "IRTC", "ZD", "FRME", "KLIC", "GNW", "VAL", "INTA", "DOCN", "CDE", "BKU", "POWL", "HWKN", "FLYW",
    "ARCB", "EPAC", "MTX", "JJSF", "YELP", "VC", "BOH", "LAUR", "SHO", "WERN", "AIN", "IPAR", "TTMI", "HUT", "RRR",
    "ICFI", "AMR", "TBBK", "PTGX", "CPRX", "LMND", "CXW", "NATL", "IBTX", "CAKE", "FFBC", "CCS", "AVPT", "ACLS", "DYN",
    "WAFD", "CABO", "PHIN", "AHR", "SBCF", "EWTX", "YOU", "BANC", "CURB", "EFSC", "SXI", "HI", "AIR", "CRGY", "VSH",
    "PPBI", "RUN", "TFIN", "IDYA", "VIAV", "MTRN", "IOVA", "PSMT", "TDW", "STNG", "WNS", "GERN", "GPOR", "EVTC", "KMT",
    "MGNI", "NEO", "IGT", "STRA", "EXTR", "WSBC", "CNMD", "CON", "KNTK", "IESC", "ROIC", "LGIH", "ALKT", "KAR", "KWR",
    "TMDX", "NMRK", "PLUS", "B", "HLMN", "PFS", "PRKS", "BANR", "GBX", "GOLF", "MCY", "HURN", "PRVA", "ROCK", "LGND",
    "SEM", "IVT", "SYBT", "SKWD", "AKRO", "FBK", "UPWK", "KYMR", "GRBK", "MBC", "MRCY", "RAMP", "ADUS", "WRBY", "OMCL",
    "AGM", "VYX", "UFPT", "RNST", "KROS", "JBLU", "ACAD", "DRH", "AVDX", "BATRK", "DBRG", "LMAT", "BEAM", "SMR", "OSW",
    "NBTB", "PRG", "CALX", "ALG", "TRMK", "RXRX", "DEI", "HEES", "ROG", "PD", "VSEC", "TNDM", "ACHR", "WULF", "TARS",
    "VERA", "LC", "VRNT", "TDOC", "NTB", "APGE", "LZB", "ABR", "APOG", "TRUP", "TGLS", "AGX", "SUPN", "FL", "OI",
    "JANX", "CASH", "PDCO"
]

# write_sp500_data(stock_picks, 'year', 5) #write the data to a csv file
balls = get_optimal_weights() 
dict(sorted(balls.items(), key=lambda item: item[1]))
data = csv_weighted_portfolio('StockPortfolio_5year_close_prices.csv', balls) #access the data from the csv file
# print(data[0][0]) 

trade_logs, tradesTally = track_trades(data[0][0], initial_investment=1000)
# print(trade_logs)
# tickers_data = individual_stock_prep_plot(['WBA','AAPL'], halflife_days=20, initial_investment=1000)
tickers_data = [] #for now we will not use this data
spy_data = individual_stock_prep_plot(['SPY'],halflife_days=20, initial_investment=1000) #add SPY to the list of stock symbols for comparison as it is the S&P 500 ETF
combined_data = data + tickers_data + spy_data #combine the data
plot_returns(combined_data, trade_logs=trade_logs, trades_tally=tradesTally) 
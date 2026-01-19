import pandas as pd


def merge_near_duplicates(group):
    # Fill missing values with the next value then take the first row
    with pd.option_context("future.no_silent_downcasting", True):
        group = group.bfill().ffill().infer_objects(copy=False)
    return group.iloc[0]


def deduplicate(df, key=None):
    if key is None:
        key = df.index.name
    original_index = df.index.name or "index"
    df = df.reset_index()
    merged_df = df.groupby(key).apply(merge_near_duplicates)
    merged_df = merged_df.reset_index(drop=True)
    merged_df = merged_df.set_index(original_index)
    return merged_df

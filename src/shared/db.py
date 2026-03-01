import boto3


dynamodb = boto3.resource("dynamodb")


def table(table_name: str):
    return dynamodb.Table(table_name)

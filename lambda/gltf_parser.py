def handler(event, context):
    print("Lambda triggered by S3 event:")
    print(event)
    return {
        'statusCode': 200,
        'body': 'Success'
    }